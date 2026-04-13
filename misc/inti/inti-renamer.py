# INTI HASH RENAMER
# - reads from names.txt
# - finds files in subdirs to rename and makes a rename list (use -a to actually rename)
#
#
# Names are rarely found in the exe as debug strings, but they often use common patterns:
#   SoundAssets/(game-id)/stream/(game-id)_BGM_01.bigrp
#   SoundAssets/(game-id)/stream/(game-id)_BGM_02_LP.bigrp
#   ...
#   (game-id).bisar
#   ...
#
# So you can use/modify other game's list (see subdir)
# Paths like Blah/Blah are also automatically split.

import os, sys, glob, struct, argparse, hashlib, pathlib, re

NAMES_LIST = 'names.txt'

DEFAULT_NAMES = [
    'GVFSP GV1 GV2 GV3 RCG YHN yhn GVA2 gva2 GGAC ggac GGR BSM3 BSM2 BSM BSM1 RRG QON GGAC2',
    'SoundAssets stream Stream',
    'boot demo bs eff em pl mbs set ui UI Shader Text MAP OBJ Font Trial CGAssets Material',
    'set_01 st_j01 st_j02 st_j03 st_j04',
    'FZXSSB_Big5 FZSS_GB18030 red white black button game title',
    'japanese english chinese common',
    'Win NX ORBIS Prospero GDKScarlett GDKXboxOne',
    #---
    'GROUP_BASE.bigrp',
    'GROUP_COMMON.bigrp',
    'GROUP_DEBUG.bigrp',
    'GROUP_ENDING.bigrp',
    'GROUP_STG.bigrp',
    'GROUP_STG_COMMON.bigrp',
    'GROUP_TITLE.bigrp',
    'GROUP_BASE.sndGrp',
    'GROUP_COMMON.sndGrp',
    'GROUP_DEBUG.sndGrp',
    'GROUP_ENDING.sndGrp',
    'GROUP_STG.sndGrp',
    'GROUP_STG_COMMON.sndGrp',
    'GROUP_TITLE.sndGrp',
    'GROUP_VOICE.sndGrp',
    'GROUP_VOICE_VE.sndGrp',
    'GROUP_VOICE_VJ.sndGrp',
    'GROUP_STG_COMMON.sndGrp',
    'GROUP_TITLE.sndGrp',
]

#DEFAULT_NAMES_ = [
#    'Streams streams STREAMS SFX sfx sound Sound Sounds SOUND SOUND SOUNDS',
#    'VOICE GROUP group Group VOICE Voice voice VE VJ VOICE_VE VOICE_VJ SFX GROUPS groups Groups VO vo',
#    'Sound Sounds Win Windows ORBIS Steam STEAM Sounds SOUNDS sounds Assets ASSETS assets COMMON common Common',
#    'ja en fr it de es pt ru nl zh_cn zh_tw ko',
#]

#---

def hash_md5(bstr):
    return hashlib.md5(bstr).hexdigest()

def hash_inti(bstr):
    hash = 0xCDE723A5
    for i in range(len(bstr)):
        temp = (hash + bstr[i]) & 0xffffffff
        hash = (141 * temp) & 0xffffffff

    return format(hash, "08x")

#---

def split_line(line, args):
    # inti hashes are case sensitive
    #if args.lowercase:
    #    line = line.lower()

    # md5 games hash full paths, while custom hash doesn't
    if not args.use_md5:
        parts = re.split(r"[ ]+", line)
    else:
        parts = re.split(r"[ /]+", line)

    if line not in parts:
        parts += [line]

    for part in list(parts):
        parts.append(line.replace('_bigrp', '.bigrp'))

    if args.name_variations:
        for part in list(parts):
            parts.extend([part.lower(), part.upper(), part.capitalize()]) #.title(), .swapcase()
            parts.extend(re.split(r"[_.]+", part))

    return parts

def generate_hashes(args):
    lines = []
    try:
        names = NAMES_LIST
        first_line = False
        with open(names, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                if not first_line and line.startswith('#@md5'):
                    args.use_md5 = True
                    continue
                first_line = True

                parts = split_line(line, args)
                lines.extend(parts)
    except FileNotFoundError as e:
        print('name list %s failed to load' % names)

    for line in DEFAULT_NAMES:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = split_line(line, args)
        lines.extend(parts)


    hashes = {}
    for line in lines:
        bstr = line.encode('utf-8')

        if args.use_md5:
            hash = hash_md5(bstr)
        else:
            hash = hash_inti(bstr)

        if hash in hashes:
            continue
        hashes[hash] = line
           

    return hashes

# handle common rename formats:
#  (filehash)
#  (filehash)~(fullhash)
#  (filehash)__(subfile)
#  (filehash)__(subfile)~(fullhash)
#  (filename)__(subfile)
#  (filename)__(subfile)~(fullhash)
def add_parts_basename(basename, ext, hashes, parts):
    basehash, sep, fullhash = basename.partition("~")
    bsubhash, sep, subfile = basehash.rpartition("__")
    if not subfile or not subfile.isdigit() or len(subfile) >= 7:
        subfile = None
    else:
        basehash = bsubhash

    fullpart = hashes.get(fullhash)
    namepart = hashes.get(basehash)

    # (string)_(subfile)~(fullname) > (string)/(fullname)
    if subfile and fullpart:
        if not namepart:
            namepart = basehash
        namepart = namepart.replace('.', '_') #folder names with dots are a bit buggy on windows
        parts.append(namepart)

        items = fullpart.split('_sndGrp_')
        if len(items) == 2:
            part = items[1]
            part = part.replace('_bigrp', '.bigrp')
            parts.append(part)
        else:
            parts.append(fullpart)
        return True

    # (string)_(subfile)
    if subfile:
        if not namepart:
            return None #nothing to rename, leave it as-is
        # add back parts
        if subfile:
            namepart += "__" + subfile
        if fullhash:
            namepart += "~" + fullhash
        if ext:
            namepart += ext
        parts.append(namepart)
        return True

    # (string)~(fullname) > (fullname)
    if fullpart:
        items = fullpart.split('_sndGrp_')
        if len(items) == 2:
            part = items[1]
            part = part.replace('_bigrp', '.bigrp')
            parts.append(part)
        else:
            parts.append(fullpart)
        return True

    if namepart:
        if '.' not in namepart:
            namepart += ext
        parts.append(namepart)
        return True

    return False


def generate_renamed_path(src_path, hashes):

    if src_path.is_dir():
        folders = src_path.parts
        basename = None
    else:
        folders = src_path.parent.parts
        basename = src_path.stem # without extension (added after decrypting)

    parts = []

    # add folders
    for folder in folders:
        part = hashes.get(folder.lower())
        if not part:
            part = folder
        parts.append(part)

    if basename:
        ok = add_parts_basename(basename, src_path.suffix, hashes, parts)
        if not ok:
            # add default in case folders did change
            parts.append(src_path.name)
            #return None

    dst_path = pathlib.Path(*parts)
    return dst_path


def generate_renames(filenames, hashes):
    renames = []
    for filename in filenames:
        src_path = pathlib.Path(filename)
        dst_path = generate_renamed_path(src_path, hashes)
        
        if src_path == dst_path: 
            continue
        renames.append( (src_path, dst_path) )

    # sort by folders last
    renames = sorted(renames, key=lambda items: (items[0].is_dir()))

    return renames

def parse():
    description = (
        "renames init creates hashed filenames"
    )

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("files", help="files to get (wildcards work)", nargs='*', default=["Data/**/*"])
    parser.add_argument("-a","--apply-rename", help="actually rename files if hash is found (defaults to print info only)", action='store_true')
    parser.add_argument("-pm","--print-missing", help="print only missing files", action='store_true')
    parser.add_argument("-pv","--print-valid", help="print only valid files", action='store_true')
    parser.add_argument("-nv","--name-variations", help="use name variations such as different cases (may add false positives)", action='store_true')
    parser.add_argument("-hi","--hash-input", help="hash name input (for debug)", action='store_true')
    args = parser.parse_args()

    args.use_md5 = False
    return args


def main():
    args = parse()

    if args.hash_input:
        for file in args.files:
            bstr = file.encode('utf-8')
            hash = hash_inti(bstr)
            print(hash, file)
        return

    filenames = []
    for file in args.files:
        filenames += glob.glob(file, recursive=True)

    hashes = generate_hashes(args)

    renames = generate_renames(filenames, hashes)

    if not args.apply_rename:
        for src_path, dst_path in renames:
            if args.print_valid and not dst_path:
                continue
            if args.print_missing and dst_path:
                continue
            print(src_path, '>', dst_path)

    if args.apply_rename:
        print("renaming files...")
        for src_path, dst_path in renames:
            # rename file
            if not dst_path:
                continue
            if not args.apply_rename:
                continue
            if not src_path.exists():
                continue

            try:
                if src_path.is_dir():
                    if any(src_path.iterdir()):
                        continue
                    src_path.rmdir()
                else:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    src_path.rename(dst_path)
            except FileExistsError:
                print('file already exists: ', src_path, '>', dst_path)


if __name__ == "__main__":
    main()
