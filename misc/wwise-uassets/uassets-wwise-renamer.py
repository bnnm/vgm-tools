# Renames .bnk + .wem from Unreal Engine 5 .uassets extracted by uassets-wwise-dumper.py
#
# Needs banks.xml (wwiser.py -r *.bnk) to find out real .wem IDs
# Note that this means unused .wem not referenced by any .bnk can't be renamed
#
#------------------------------------------------------------------------------

import argparse, sys, json, glob, os, struct
import xml.etree.ElementTree as ET

DEFAULT_BANKS_FILE = 'banks.xml'
BNKS_CACHE_FILE = 'cache.bnks.json'
WEMS_CACHE_FILE = 'cache.wems.json'
OUTPUT_DIR = '_out/Wwise/'
DUPES_DIR = '_dupes/'
DUPES_PRE_DIR = '_dupes/prefetch/'
UNKNOWNS_DIR = '_unknowns/'
RENAME_PREFETCH = False #TODO: not fully ok

#------------------------------------------------------------------------------

class MediaInfo:
    def __init__(self):
        self.sourceID = None
        self.cacheID = None
        self.bIsLanguageSpecific = None
        #self.uInMemoryMediaSize = None
        # note that UE can set StreamType=bnk but memory .wem be in uasset/ubulk
        #self.StreamType = None

class BankInfo:
    def __init__(self):
        self.path = None

        self.dwSoundBankID = None
        self.dwSoundBankName = None
        self.dwLanguageID = None
        self.dwLanguageName = None

        self.medias = []

    def get_lang(self):
        if self.dwLanguageID == 393239870: #sfx
            lang = ''
        elif self.dwLanguageName:
            lang = self.dwLanguageName
        else:
            lang = str(self.dwLanguageID) # TODO: improve (wwise should have most langs tho)
        return lang

    def get_name(self):
        if self.dwSoundBankName:
            name = self.dwSoundBankName
        else:
            name = str(self.dwSoundBankID)
        return name

class WemInfo:
    def __init__(self):
        self.path = None
        
        self.hash0 = None
        self.hash1 = None
        self.hash2 = None
        self.hash3 = None

        self.size = None
        self.is_memory = False

#------------------------------------------------------------------------------

# ugly serialization crap b/c python sucks
CLASS_REGISTRY = {
    "BankInfo": BankInfo,
    "MediaInfo": MediaInfo,
    "WemInfo": WemInfo,
}

def cache_serialize(obj):
    if isinstance(obj, list):
        return [cache_serialize(x) for x in obj]

    if hasattr(obj, "__dict__"):
        return {
            "__class__": obj.__class__.__name__,
            **{
                k: cache_serialize(v)
                for k, v in obj.__dict__.items()
            }
        }

    return obj

def cache_deserialize(data):
    if isinstance(data, list):
        return [cache_deserialize(x) for x in data]

    if isinstance(data, dict):
        class_name = data.get("__class__")

        if class_name:
            cls = CLASS_REGISTRY[class_name]
            obj = cls()

            for key, value in data.items():
                if key != "__class__":
                    setattr(obj, key, cache_deserialize(value))

            return obj

        return {
            k: cache_deserialize(v)
            for k, v in data.items()
        }

    return data

def cache_save(items, filename):
    try:
        with open(filename, "w") as f:
            json.dump(cache_serialize(items), f)
    except:
        print("couldn't save cache")

def cache_load(filename):
    try:
        with open(filename) as f:
            return cache_deserialize(json.load(f))    
    except:
        return None

#------------------------------------------------------------------------------

class MissingDataError(ValueError):
    pass

# read bank info from the xml
def read_banks(xml_path):
    banks = []

    #TODO: streaming parser? (less memory but also slow?)
    try:
        tree = ET.parse(xml_path)
    except:
        raise MissingDataError(f"couldn't read {xml_path} (generate with wwiser first)")

    src = tree.getroot()
    base = src.findall('base')[0] #after N objects is a single <base>
    
    for root in base.findall('root'):
        basename = root.attrib.get('filename')
        path = root.attrib.get('pa')

        # renamed .bnk can be used for .wem info
        #if '#' not in basename:
        #    continue

        bank = BankInfo()
        banks.append(bank)
        bank.path = os.path.join(path, basename).replace('\\', '/')


        # all obj inside root
        for obj in root.iter('obj'):

            # unique bank header per root
            if obj.attrib.get('na') == 'AkBankHeader':
                for fld in obj.iter('fld'):
                    if fld.attrib.get('na') == 'dwSoundBankID':
                        bank.dwSoundBankID = int(fld.attrib.get('va'))
                        bank.dwSoundBankName = fld.attrib.get('hn')

                    if fld.attrib.get('na') == 'dwLanguageID':
                        bank.dwLanguageID = int(fld.attrib.get('va'))
                        bank.dwLanguageName = fld.attrib.get('hn')

                continue

            # source info for AkSound or AkMusicTrack
            if obj.attrib.get('na') == 'AkMediaInformation': #'AkBankSourceData':
                mda = MediaInfo()
                for fld in obj.iter('fld'):
                    if fld.attrib.get('na') == 'sourceID':
                        mda.sourceID = int(fld.attrib.get('va'))

                    if fld.attrib.get('na') == 'cacheID':
                        mda.cacheID = int(fld.attrib.get('va'))

                    #if fld.attrib.get('na') == 'uInMemoryMediaSize':
                    #    mda.uInMemoryMediaSize = int(fld.attrib.get('va'))

                    if fld.attrib.get('na') == 'bIsLanguageSpecific':
                        mda.bIsLanguageSpecific = int(fld.attrib.get('va'))

                bank.medias.append(mda)
                continue

    return banks


def load_bnks(args):
    print("loading bnk info")

    bnks = None
    if args.cache:
        bnks = cache_load(BNKS_CACHE_FILE)

    if bnks:
        print('loaded bnk info from cache')
    else:
        bnks = read_banks(args.banks)

        if args.cache:
            cache_save(bnks, BNKS_CACHE_FILE)
        print('loaded bnk info from xml')
    return bnks

#------------------------------------------------------------------------------

# Read .wem's info, including 'hash' chunk (which can be used to get a wem's cacheID).
# Multiple .wem can have the same hash since both memory and streamed .wem may
# coexist in the same ubulk.
def read_wems():
    wems = []

    files = glob.glob("**/*.wem", recursive=True)
    for path in files:
        basename = os.path.basename(path)

        # non-renamed files should include a '#' (maybe should use base folder instead?)
        if '#' not in basename:
            continue

        wem = WemInfo()
        wems.append(wem)

        wem.path = path.replace('\\', '/')
        try:
            with open(path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                wem.size = f.tell()
                f.seek(0, os.SEEK_SET)

                header = f.read(0x100)

            # TODO: maybe should parse the RIFF header, but probably fine
            index = header.find(b'hash')
            if index == -1:
                print(f"{path}: 'hash' not found in first bytes")
                continue

            chunk_size = struct.unpack_from('<I', header, index + 0x04)[0]
            if chunk_size != 0x10:
                print(f"{path}: 'hash' found but chunk_size is not 0x10")
                continue

            v0, v1, v2, v3 = struct.unpack_from('<IIII', header, index + 0x08)

            wem.hash0 = v0
            wem.hash1 = v1
            wem.hash2 = v2
            wem.hash3 = v3

        except Exception as e:
            print(f"Error processing {path}: {e}")

    return wems
   

# create a 'key' for a filename, to group by uasset_name when possible
# files are expected to be named like: (path)/(uasset_name)-#(number).(ext)
def get_path_key(path):
    key = path
    #key = os.path.basename(key)
    key = os.path.splitext(key)[0]
    key = key.rsplit('-#', 1)[0]
    #key = os.path.dirname(path)
    return key

# Find multiple .wem with same hash and mark pretech ones
def mark_memory_wems(wems):
    items = {}
    
    # group wem by path,hash
    for wem in wems:
        # Typically memory and stream .wem are part of the same uasset+ubulk,
        # but unsure if always; detect them regardless of uasset
        #path_key = get_path_key(wem.path)
        path_key = ''
        key = (path_key, wem.hash0, wem.hash1, wem.hash2, wem.hash3)
        items.setdefault(key, []).append(wem)

    # Find dupes of the same hash and mark smallest wem as memory.
    # Memory and stream .wem can be in the same .ubulk, so no proper way to detect them
    # .bnk may also consider stream .wem as 'memory' as well.
    for wem_list in items.values():
        if len(wem_list) <= 0:
            continue

        min_size = min(wem.size for wem in wem_list)
        max_size = max(wem.size for wem in wem_list)

        # multiple dupes of same size is normal
        if min_size == max_size:
            continue

        for wem in wem_list:
            wem.is_memory = wem.size == min_size


def load_wems(args):
    print("loading wem info")

    wems = None
    if args.cache:
        wems = cache_load(WEMS_CACHE_FILE)

    if wems:
        print('loaded wem data from cache')
    else:
        wems = read_wems()
        
        if args.cache:
            cache_save(wems, WEMS_CACHE_FILE)
        print('loaded wem data from paths')

    mark_memory_wems(wems)
    return wems

#------------------------------------------------------------------------------

#TODO: improve
def is_ignorable_path(src):
    if src.startswith(DUPES_DIR):
        return True
    if src.startswith(UNKNOWNS_DIR):
        return True
    return False

def make_renames_bnks(bnks):
    items = []
    dsts = set()

    for bnk in bnks:
        src = bnk.path
        
        dir = os.path.dirname(src)
        basename = os.path.basename(src)
        ext = os.path.splitext(basename)[1]

        if bnk.dwLanguageID is None or bnk.dwSoundBankID is None:
            raise ValueError("bank was incorrectly loaded")

        lang = bnk.get_lang()
        name = bnk.get_name()

        dst = os.path.join(dir, lang, name + ext)

        # somehow in some ubulk there are copies of sfx bank (exact same)
        if dst in dsts:
            if src.startswith(OUTPUT_DIR):
                dst = os.path.join(DUPES_DIR, src[len(OUTPUT_DIR):])
            else:
                dst = os.path.join(DUPES_DIR, src)
        else:
            dsts.add(dst)

        if is_ignorable_path(src):
            continue

        items.append( (src, dst) )
        
    return items

def find_rename_medias(wem, bnks):
    mdas = []
    if not bnks:
        return mdas

    for bnk in bnks:
        for mda in bnk.medias:
            if mda.cacheID != wem.hash0:
                continue
            mdas.append( (bnk, mda) )

    return mdas

def make_rename_wem(wem, bnk, mda):
    src = wem.path
    
    lang = ''
    if mda.bIsLanguageSpecific:
        lang = bnk.get_lang()
    
    name = str(mda.sourceID)
    if wem.is_memory:
        name += '[pre]'

    dir = os.path.dirname(src)
    basename = os.path.basename(src)
    ext = os.path.splitext(basename)[1]

    dst = os.path.join(dir, lang, name + ext)
    dst = dst.replace("\\","/")
    
    return dst
    

def make_renames_wems(bnks, wems):
    items = []
    dsts = set()
    unknowns = []
    dupes = []

    # group bnk per asset, as .wem+bnk from same .uasset+ubulk are often together.
    # WwiseMultiReferenceAssetLibrary may only have .wem though, and some ubulk
    # have .wem that aren't used at all (for example unfinished DLC).
    # Renames also handle below if .wem+bnk aren't grouped together, so just in case.
    bnks_dir = {}
    for bnk in bnks:
        path_key = get_path_key(bnk.path)
        bnks_dir.setdefault(path_key, []).append(bnk)

    # find .wem ID from bnks
    for wem in wems:
        path_key = get_path_key(wem.path)
        bnks_list = bnks_dir.get(path_key)

        # somewhat common (files in different .uasset+ubulk)
        if not bnks_list:
            bnks_list = bnks

        # find candidate sourceIDs from cacheIDs
        mdas = find_rename_medias(wem, bnks_list)
        if not mdas:
            #print("no bnk in path for:", wem.path) # ?
            mdas = find_rename_medias(wem, bnks)

        # cacheID not referenced by any .bnk (possible for unused .wem)
        if not mdas:
            unknowns.append(wem)

        # get first usable wem name
        src = wem.path
        dst = None
        for bnk, mda in mdas:
            dst_test = make_rename_wem(wem, bnk, mda)

            # multiple sourceIDs for the same cacheID is possible with dupes,
            # so detect already renamed .wem (either physical or pending)
            if dst_test in dsts:
                continue
            if os.path.isfile(dst_test):
                continue
            dst = dst_test
            break

        # treat prefetch files as dupes
        if not RENAME_PREFETCH and wem.is_memory:
            dupes.append(wem)
            continue

        # every sourceID was 'used', usually happens in localized .bnk using non-localized .wem
        if not dst:
            dupes.append(wem)
            continue

        # treat prefetch files as dupes after renaming #TODO: has issues with multidupes
        if '[pre]' in dst:
            dst_dir = DUPES_DIR if not wem.is_memory else DUPES_PRE_DIR

            if dst.startswith(OUTPUT_DIR):
                dst = os.path.join(dst_dir, dst[len(OUTPUT_DIR):])
            else:
                dst = os.path.join(dst_dir, dst)
            dupes.append(wem)

        if is_ignorable_path(src):
            continue

        dsts.add(dst)
        items.append( (src, dst) )

    # no .bnk point to these .wem
    # manually deserializing .uasset classes for the ID is probably the only way,
    # then again, no .bnk = no .txtp either so usually not a big real
    if unknowns:
        print(f"couldn't rename {len(unknowns)} .wem (missing .bnk; sourceID may be in .uasset)")
    for wem in unknowns:
        src = wem.path
        if src.startswith(OUTPUT_DIR):
            dst = os.path.join(UNKNOWNS_DIR, src[len(OUTPUT_DIR):])
        else:
            dst = os.path.join(UNKNOWNS_DIR, src)
        items.append( (src, dst) )

    for wem in dupes:
        src = wem.path
        dst_dir = DUPES_DIR if not wem.is_memory else DUPES_PRE_DIR
        
        if src.startswith(OUTPUT_DIR):
            dst = os.path.join(dst_dir, src[len(OUTPUT_DIR):])
        else:
            dst = os.path.join(dst_dir, src)
        items.append( (src, dst) )

    return items

# rename .wem using .bnk info, considering:
# - bnk hash cacheID (hash0) <> sourceId (.wem name)
# - .wem can be reused with same hash but different sourceId
#   - sometimes happens for localized .wem
# - .wem can be reused with same hash and *same* sourceId
#   - happens when repeating wem in different OR same uasset/ubulk
#   - ex. a silent wem hash same sourceId + cacheID and is cloned multiple times for EN and JP langs
#     (so when matching, it may take any of the .wem)
# - localized bnk and wem are in the same folder, with same names
# - localized .wem can be repeated (see above)
#   - ex. a EN+JP bnk use 2 wem, one with localized flag and other non-localized.
#     the non-localised one is exactly the same, but ends up being reused
# - some .wem and .bnk can be already renamed
# - bnk must also be renamed
def make_renames(bnks, wems):
    print("preparing renames")

    items = []
    
    items += make_renames_bnks(bnks)
    items += make_renames_wems(bnks, wems)

    return items


#------------------------------------------------------------------------------

def rename_files(args, items):
    print("renaming files")

    for src, dst in items:
        # ignore non-renamed files
        src_basename = os.path.basename(src)
        if '#' not in src_basename:
            continue

        if src == dst:
            continue

        # already renamed
        if not os.path.isfile(src):
            continue

        # double dupes name? renamed
        if os.path.isfile(dst):
            print("warning: filename already exists")
            print(f'  src: {src}\n  dst: {dst}')
            continue

        if args.list:
            print(f'- {src}\n  {dst}')
            continue

        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(src, dst)
        except:
            print("couldn't rename file")
            print(f'  src: {src}\n  dst: {dst}')

#------------------------------------------------------------------------------

def parse():
    p = argparse.ArgumentParser(description="Renames Wwise bnk/wem based on banks.xml")
    p.add_argument("banks", nargs="?", default=DEFAULT_BANKS_FILE, help="banks.xml file")
    p.add_argument("-l", "--list", action="store_true", help="list items only and don't unpack")
    p.add_argument("-c", "--cache", action="store_true", help="save bnk/wem info to cache (faster tests)")
    return p.parse_args()

def main():
    args = parse()

    try:
        # get bnk info from xml
        bnks = load_bnks(args)

        # get wem info from paths
        wems = load_wems(args)

        # match both and rename files
        items = make_renames(bnks, wems)

        # actual renaming
        rename_files(args, items)

    except MissingDataError as e:
        print("WARNING:", str(e))

if __name__ == "__main__":
    main()
