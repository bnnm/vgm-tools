# makes !diff.txt with info from files in 2 folders
# - put files in "OLD" dir
# - put files to compare in "NEW" dir
# - run

import glob, hashlib, re, os


dir_old = 'OLD'
dir_new = 'NEW'
chunk = 0x10000
move = True


def get_hash(file):
    hasher = hashlib.md5()
    with open(file, 'rb') as f:
        while True:
            data = f.read(chunk)
            if not len(data):
                break
            hasher.update(data)
    return hasher.hexdigest()

def get_items(path):
    items = [] #not dict in case of dupes
    files = glob.glob(path)
    files.sort()
    for file in files:
        #ext = os.path.splitext(os.path.basename(file))[1]
        #if ext in ignore_exts:
        #    continue

        hash = get_hash(file)
        base = os.path.basename(file)
        items.append( (hash, file, base) )
    return items


def main():
    items_old = get_items(dir_old + '/*.*')
    items_new = get_items(dir_new + '/*.*')

    
    diffs = []
    missing_old = []
    missing_new = []
    for hash_old, file_old, base_old in items_old:
        for hash_new, file_new, base_new in items_new:
            if hash_new == hash_old:
                continue
            if base_new == base_old:
                diffs.append(base_new)

    for hash_old, file_old, base_old in items_old:
        found = False
        for hash_new, file_new, base_new in items_new:
            if base_new == base_old:
                found = True
                break
        if not found:
            missing_old.append(base_old)

    for hash_new, file_new, base_new in items_new:
        found = False
        for hash_old, file_old, base_old in items_old:
            if base_new == base_old:
                found = True
                break
        if not found:
            missing_new.append(base_new)
            
    if move:
        mkdir_old = dir_old + "/diffs"
        mkdir_new = dir_new + "/diffs"
        os.makedirs(mkdir_old, exist_ok=True)
        os.makedirs(mkdir_new, exist_ok=True)
        for file in diffs:
            os.rename(dir_old + "/" + file, mkdir_old + "/" + file)
            os.rename(dir_new + "/" + file, mkdir_new + "/" + file)

        mkdir_old = dir_old + "/extra"
        mkdir_new = dir_new + "/extra"
        os.makedirs(mkdir_old, exist_ok=True)
        os.makedirs(mkdir_new, exist_ok=True)
        for file in missing_old:
            os.rename(dir_old + "/" + file, mkdir_old + "/" + file)
        for file in missing_new:
            os.rename(dir_new + "/" + file, mkdir_new + "/" + file)

    with open('!diffs.txt', 'w') as f:
        if diffs:
            f.write('# diffs\n')
            f.write('\n'.join(diffs))
            f.write('\n\n')
        if missing_old:
            f.write('# extra in old\n')
            f.write('\n'.join(missing_old))
            f.write('\n\n')
        if missing_new:
            f.write('# extra in new\n')
            f.write('\n'.join(missing_new))
            f.write('\n\n')

if __name__ == "__main__":
    main()
