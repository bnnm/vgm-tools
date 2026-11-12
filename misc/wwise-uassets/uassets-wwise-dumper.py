# Dumps 'rough' Wwise data from Unreal Engine 5 .uasset.
#
# Use for certain UE+Wwise versions that are hard to extract (try FModel + usmap first).
#
# Extracted files don't have proper Wwise IDs, so they can't be used with wwiser as-is.
# However uassets-wwise-renamer.py can rename them, with help from Wwiser.
#
# Due to how uassets works many files will have dupes; will be handled when renaming.
# Similarly, sometimes .uasset and .bnk reference .wem that don't exists, this isn't a bug but a Wwise quirk.
#
# NOTE: extraction may not work for all UE5 .uasset types at the moment.
#
#------------------------------------------------------------------------------

import os, argparse, glob, struct

DEFAULT_FILES = "**/*.uasset"
DEFAULT_OUTPUT_DIR = '_out/Wwise/'

DEFAULT_EXTS = {
    b'BKHD': '.bnk',
    b'RIFF': '.wem',
}
DEFAULT_EXT = '.bin'
DEFAULT_EXT_WAV = '.wav'
PATH_LIMIT = 250 - 8 - 5


# TODO: improve detection
IS_UE53 = True
IS_UE54 = True
HAS_BULK_DATA_MAP = True


#PRINT_SKIPS = ['files']
PRINT_SKIPS = []

#------------------------------------------------------------------------------

def read_utf16(f, size):
    bytes = f.read(size)
    return bytes.decode('utf-16')

def read_utf8(f, size):
    bytes = f.read(size)
    return bytes.decode('utf-8')

def read_skip(f, size):
    pos = f.tell() + size
    f.seek(pos)

def read_u16be(f):
    data = f.read(2)
    return struct.unpack(">H", data)[0]

def read_u32(f):
    data = f.read(4)
    return struct.unpack("<I", data)[0]

def read_u64(f):
    data = f.read(8)
    return struct.unpack("<Q", data)[0]


#------------------------------------------------------------------------------

class Printable:
    skips = PRINT_SKIPS

    def _load_int(self, val, prefix, attrs):
        attrs.append(f"{prefix}{hex(val)}")

    def _load_list(self, val, pad, attrs, prefix):
        if not val:
            attrs.append(f"{prefix}[]")
            return
        
        attrs.append(f"{prefix}[")
        for item in val:
            self._load_repr(item, pad + 2, attrs, key=None)
        attrs.append(f"{' ' * pad}]")

    def _load_object(self, val, pad, attrs, prefix):
        attrs.append(f"{prefix}{val.__class__.__name__}")
        for child_key, child_val in vars(val).items():
            self._load_repr(child_val, pad + 2, attrs, key=child_key)

    def _load_repr(self, val, pad, attrs, key=None):
        if key in self.skips:
            return
        
        if key is not None:
            prefix = f"{' ' * pad}{key} = "
        else:
            prefix = f"{' ' * pad}"

        if isinstance(val, int) and not isinstance(val, bool):
            self._load_int(val, prefix, attrs)
            return

        if isinstance(val, list):
            self._load_list(val, pad, attrs, prefix)
            return

        if hasattr(val, '__dict__') and not isinstance(val, (str, dict)):
            self._load_object(val, pad, attrs, prefix)
            return

        attrs.append(f"{prefix}{val}")

    def __str__(self):
        attrs = [f"{self.__class__.__name__}"]
        base_pad = 2

        for key, value in vars(self).items():
            self._load_repr(value, base_pad, attrs, key=key)

        return "\n".join(attrs)

#------------------------------------------------------------------------------

# https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/CoreUObject/EBulkDataFlags
# https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/Assets/Objects/EBulkDataFlags.cs
class UassetFile(Printable):
    # see docs for descriptions. most of those sound like nonsense, but generally:
    # 0x0000000 = memory, 0x00010501 = streamed in ubulk
    #None                            = 0
    PayloadAtEndOfFile               = 1 << 0   #0x00000001
    SerializeCompressedZLIB          = 1 << 1   
    ForceSingleElementSerialization  = 1 << 2
    SingleUse                        = 1 << 3
    ForceInlinePayload               = 1 << 6   #0x00000040
    #SerializeCompressed             = SerializeCompressedZLIB
    PayloadInSeparateFile            = 1 << 8   #0x00000100
    Force_NOT_InlinePayload          = 1 << 10  #0x00000400
    OptionalPayload                  = 1 << 11  #0x00000800
    MemoryMappedPayload              = 1 << 12  #0x00001000
    Size64Bit                        = 1 << 13
    DuplicateNonOptionalPayload      = 1 << 14
    NoOffsetFixUp                    = 1 << 16  #0x00010000
    WorkspaceDomainPayload           = 1 << 17
    LazyLoadable                     = 1 << 18
    AlwaysAllowDiscard               = 1 << 28
    DataIsMemoryMapped               = 1 << 30
    UsesIoDispatcher                 = 1 << 31

    def __init__(self):
        pass

    def parse(self, f):
        self.offset = read_u64(f)
        self.unknown = read_u64(f)
        self.size = read_u64(f)
        self.flags = read_u64(f)
        
        self.is_ubulk = self.flags & self.PayloadInSeparateFile != 0
        self.is_compressed = self.flags & self.SerializeCompressedZLIB != 0

# https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/IO/Objects/FZenPackageSummary.cs
# https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/IO/Objects/FBulkDataMapEntry.cs
# https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/Assets/IoPackage.cs
class UassetHeader(Printable):
    def __init__(self):
        pass

    def _has_cell_offsets(self, f):
        f.seek(0x3C)
        test1 = read_u32(f)
        test2 = read_u32(f)
        test3 = read_u64(f)
        f.seek(0x00)

        if test1 > test2 and test1 > 0x100:
            return False
        if test3 != 0x00000000C1640000:
            return False
        return True


    def parse(self, f):
        #f.seek(0x00, os.SEEK_END)
        #size  = f.tell()
        #f.seek(0x00)

        self.has_cell_offsets = self._has_cell_offsets(f)

        # 00
        self.bHasVersioningInfo = read_u32(f)
        self.HeaderSize = read_u32(f)
        self.NameIndex = read_u32(f)
        self.NameNumber = read_u32(f)

        # 10
        self.PackageFlags = read_u32(f)
        self.CookedHeaderSize = read_u32(f)
        self.ImportedPublicExportHashesOffset = read_u32(f)
        self.ImportMapOffset = read_u32(f)

        # 20
        self.ExportMapOffset = read_u32(f)
        self.ExportBundleEntriesOffset = read_u32(f)
        if IS_UE53:
            self.DependencyBundleHeadersOffset = read_u32(f)
            self.DependencyBundleEntriesOffset = read_u32(f)
            self.ImportedPackageNamesOffset = read_u32(f)

            self.GraphDataOffset = None
        else:
            self.GraphDataOffset = read_u32(f)
            self.DependencyBundleHeadersOffset = None
            self.DependencyBundleEntriesOffset = None
            self.ImportedPackageNamesOffset = None

        # 
        if self.bHasVersioningInfo:
            #raise ValueError("versioning info found") #not seen

            ZenVersion = read_u32(f)
            PackageVersion = read_u32(f)
            LicenseeVersion = read_u32(f)
            CustomVersionCount = read_u32(f)
            for i in range(CustomVersionCount):
                GUID = f.read(0x10) #read_guid()
                Version = read_u32(f)

        # 
        if self.has_cell_offsets:
            self.CellImportMapOffset = read_u32(f)
            self.CellExportMapOffset = read_u32(f)
        else:
            self.CellImportMapOffset = None
            self.CellExportMapOffset = None

        #
        self.NameCount = read_u32(f)
        self.StringBytes = read_u32(f)
        self.HashVersion = read_u64(f)
        self.hashes = []

        for i in range(self.NameCount):
            hash = read_u64(f)
            self.hashes.append(hash)

        name_sizes = []
        for i in range(self.NameCount):
            name_size = read_u16be(f)
            name_sizes.append(name_size)

        # Identifiers like properties, class names, etc. are referenced by index in serialized data.
        # ubulk_data_map 'files' are class payloads (I think), so no direct name<>file matching is possible.
        self.Names = []
        for name_size in name_sizes:
            # both name types can coexist in the same uasset (ex. Phantom Blade Zero Music*.uasset)
            if name_size & 0x8000:
                Name = read_utf16(f, (name_size & 0x7FFF) * 2)
            else:
                Name = read_utf8(f, name_size)
            self.Names.append(Name)

        # 
        if HAS_BULK_DATA_MAP:
            if IS_UE54:
                padding = read_u64(f)
                read_skip(f, padding)

            self.bulk_map_size = read_u64(f)
            self.bulk_map_count = self.bulk_map_size // 0x20
            self.files = []

            for i in range(self.bulk_map_count):
                file = UassetFile()
                file.parse(f)
                self.files.append(file)
        else:
            self.files = []

        # After ubulk map are other sections (ImportedPublicExportHashesOffset and so on). Notably,
        # after HeaderSize there is a "serialized export data" section, which contains serialized
        # classes that may include .wem IDs (not always) and maybe lang + string indexes.
        # This serialization info seems to be backed in the game (needs .usmap I think) and
        # realistically only cue4parse could handle it (may vary per game).

#------------------------------------------------------------------------------

class MissingDataError(ValueError):
    pass

def is_wwise(data):
    if data[0:4] == b'BKHD':
        return True
    if data[0:4] == b'RIFF': #only .wem with 'hash' can be used
        return b'hash' in data[:0x100]
    return False

# padding 'files' can be found sometimes
def is_empty(data, max_bytes=0x10):
    return not any(data[:max_bytes]) #safe slicing if less


def extract_uasset(args, filename, header, f_uasset, f_ubulk):
    # make output filename
    if args.dirs_uasset:
        # subdir per uasset (blah/banana.uasset -> blah/banana/banana-#0001.wem)
        basepath = os.path.splitext(filename)[0]
        basename = os.path.basename(basepath)
    else:
        # base dir (blah/banana.uasset -> blah/banana-#0001.wem)
        basepath = os.path.dirname(filename)
        basename = os.path.basename(os.path.splitext(filename)[0])
        
    # blah/banana-#0001.wem -> blah~banana-#0001.wem
    if not args.dirs_keep:
        basepath = basepath.replace('\\', '/')
        basepath = basepath.replace('/', '~')
        basename = f"{basepath}~{basename}"
        if len(args.output) + len(basename) >= PATH_LIMIT:
            limit = PATH_LIMIT - len(args.output)
            basename = basename[-limit:]
        basepath = ''

    outdir = os.path.join(args.output, basepath)
    name_width = 8 if len(header.files) >= 10000 else 4

    # process asset list and write files
    padding_count = 0
    skipped_count = 0
    for i, file in enumerate(header.files):
        if file.is_ubulk and not f_ubulk:
            raise MissingDataError(f"couldn't extract {filename}, ubulk not found")
        
        offset = file.offset
        size = file.size
        
        if file.is_ubulk:
            f_ubulk.seek(offset)
            data = f_ubulk.read(size)
        else:
            offset += header.HeaderSize
            f_uasset.seek(offset)
            data = f_uasset.read(size)
    
        # use basename to avoid name dupes in wwise
        # '-' helps wwiser get wwnames, and '#' for quick detection of unnamed files
        name = '%s-#%0*i' % (basename, name_width, i)

        # this tools was made for Wwise assets, but probably can extract anything
        wwise_asset = is_wwise(data)
        if not wwise_asset and not args.all:
            if is_empty(data):
                padding_count += 1
            else:
                skipped_count += 1
            continue

        ext = DEFAULT_EXTS.get(data[0:4], DEFAULT_EXT)
        if not wwise_asset and data[0:4] == b'RIFF': #TODO improve
            ext = DEFAULT_EXT_WAV

        os.makedirs(outdir, exist_ok=True)            
        filename_out = os.path.join(outdir, name + ext)

        with open(filename_out, 'wb') as f:
            f.write(data)

    if skipped_count:
        print(f"skipped {skipped_count} files in {filename}")
    #if padding_count:
    #    print(f"ignored {padding_count} files in {filename}")

#------------------------------------------------------------------------------

def parse_file(args, filename):
    print(f"Parsing: {filename}")
    filename_uasset = filename
    filename_ubulk  = os.path.splitext(filename)[0] + '.ubulk'

    f_uasset = None
    f_ubulk = None
    try:
        f_uasset = open(filename_uasset, "rb")
        try:
            f_ubulk = open(filename_ubulk, "rb")    
        except:
            pass

        # main references to uasset
        header = UassetHeader()
        header.parse(f_uasset)

        if args.list:
            print(header)
            return

        try:
            extract_uasset(args, filename, header, f_uasset, f_ubulk)
        except MissingDataError as e:
            print("WARNING:", str(e))
            
    finally:
        f_uasset.close()
        if f_ubulk:
            f_ubulk.close()

#------------------------------------------------------------------------------

def parse():
    p = argparse.ArgumentParser(description="Unpack Wwise bnk/wem from Unreal Engine .uasset files (needs renaming)")
    p.add_argument("files", nargs="?", default=DEFAULT_FILES, help="glob pattern or file list")
    p.add_argument("-a", "--all", action="store_true", help="extract all files instead (defaults to wwise only)")
    p.add_argument("-l", "--list", action="store_true", help="list items only and don't unpack")
    p.add_argument("-dk", "--dirs-keep", action="store_true", help="keep original paths instead of flatten (easier dupe detection but harder to navigate)")
    p.add_argument("-du", "--dirs-uasset", action="store_true", help="unpack each uasset to its own subdir")
    #p.add_argument("-o", "--output", default=DEFAULT_OUTPUT_DIR, help="output directory")
    args = p.parse_args()
    
    args.output = DEFAULT_OUTPUT_DIR #needs some changes in renames
    return args

def main():
    args = parse()

    files = glob.glob(args.files, recursive=True)

    print(f"Found {len(files)} .uasset files")

    for filename in files:
        parse_file(args, filename)

if __name__ == "__main__":
    main()
