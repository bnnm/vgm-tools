

import glob, hashlib, re, os

TEST_SEMI = False
def get_hash(file, semi=False):
    chunk = 0x10000

    if semi and not TEST_SEMI:
        return None

    hasher = hashlib.md5()
    with open(file, 'rb') as f:
        if semi:
            f.seek(0, os.SEEK_END)
            size = f.tell()     
            if size < 0x1000:
                return 0
            f.seek(0x1000, os.SEEK_SET)

        while True:
            data = f.read(chunk)
            if not len(data):
                break
            hasher.update(data)
    return hasher.hexdigest()

def get_items(path):
    items = [] #not dict in case of dupes
    files = glob.glob(path, recursive=True)
    files.sort()
    for file in files:
        #ext = os.path.splitext(os.path.basename(file))[1]
        #if ext in ignore_exts:
        #    continue
        if os.path.isdir(file):
            continue
        hash = get_hash(file)
        semihash = get_hash(file, semi=True)

        base = os.path.basename(file)
        items.append( (hash, semihash, file, base) )
    return items

def main():
    items = get_items('./**/*.*')

    dupes = {}
    semis = {}
    for hash, semihash, file, base in items:
        if hash not in dupes:
            dupes[hash] = []
        dupes[hash].append(file)
        
        if semihash:
            if semihash not in semis:
                semis[semihash] = []
            semis[semihash].append(file)

    lines = []
    for hash, semihash, file, base in items:
        lines.append(file)

        subfiles = dupes[hash]
        for subfile in subfiles:
            if subfile == file:
                continue
            dupe = " - dupe " + subfile
            lines.append(dupe)

        if semihash:
            subfiles = semis[semihash]
            for subfile in subfiles:
                if subfile == file:
                    continue
                dupe = " - semi " + subfile
                lines.append(dupe)

    with open('!diffs.txt', 'w') as f:
        f.write('\n'.join(lines))


if __name__ == "__main__":
    main()
