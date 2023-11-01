# decrypts downloaded assets

import os, subprocess, json, hashlib, glob, sys

REMOVE_ORIGINALS = False #not recommended to avoid re-decrypting files by mistake
BASE_PATH = 'bium-dl/'
DEF_FILES = 'bium-dl/**/*'
ABLIST = 'ablist.json'
ABLISTDEC = 'ablist.json.dec'


def call(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def parse_ablist():
    with open(ABLISTDEC, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # each url is in the form of (base-url)/(first-letter-of-hashname)/(hashname-of-bundlename)
    bundles = {}
    for asset in data["assetBundles"]:
        bn = asset["bundleName"]
        hash = hashlib.sha1()
        hash.update(bn.encode('utf-8'))
        bn_hash = hash.hexdigest().lower()

        # save names for later
        bundles[bn] = bn
        bundles[bn_hash] = bn
    return bundles

def get_files():
    files = []
    if len(sys.argv) > 1:
        for item in sys.argv[1:]:
            if os.path.isfile(item):
                files.append(item)
            else:
                files += glob.glob(item, recursive=True)
    else:
        files += glob.glob(DEF_FILES, recursive=True)
    return files

def decrypt_file(file, bundles):
    basename = os.path.basename(file)

    normname = file.replace('\\', '/')
    if BASE_PATH in normname:
        pos = normname.index(BASE_PATH) + len(BASE_PATH)
        partname = normname[pos:]
    else:
        partname = normname

    if basename == ABLIST:
        bundlename = basename

    elif len(basename) == 40: #sha1 hash
        bundlename = bundles.get(basename)

    else:
        bundlename = bundles.get(partname)
    
    if not bundlename: # last attempt
        for item in bundles.keys():
            if file.endswith(item):
                bundlename = item
                break

    if not bundlename:
        print("unknown file " + file)
        return

    call(['biumdec.exe', file, bundlename])
    #TODO remove original?
    
    if REMOVE_ORIGINALS:
        try:
            os.remove(file)
        except:
            pass
        try:
            os.rename(file+'.dec', file)
        except:
            pass

if __name__ == "__main__":
    bundles = parse_ablist()
    files = get_files()
    for file in files:
        decrypt_file(file, bundles)
 
