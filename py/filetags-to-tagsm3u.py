# makes !tags.m3u from "tagged" (renamed) files
# - put renamed files in "OLD" dir
# - put original names in "NEW" dir
# - run

import glob, hashlib, re, os

dir_old = 'OLD'
dir_new = 'NEW'
chunk = 0x10000

pt_tags1 = re.compile(r"([0-9][A-Za-z0-9]+)[ ]+[-]*[ ]*([A-Za-z0-9!@$%&().,']+)[ ]+[-][ ]+(.+)")
pt_tags2 = re.compile(r"([0-9][A-Za-z0-9]+)[ ]+(.+)")

ignore_exts = ['.txt', '.m3u', '.zip', '.7z', '.bms']

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
        ext = os.path.splitext(os.path.basename(file))[1]
        if ext in ignore_exts:
            continue

        hash = get_hash(file)
        items.append( (hash, file) )
    return items


def main():
    items_old = get_items(dir_old + '/*.*')
    items_new = get_items(dir_new + '/*.*')
    
    tags = []
    for hash_old, file_old in items_old:
        found = False

        base_old = os.path.basename(file_old)
        base_old = os.path.splitext(base_old)[0]

        if True:
            match = pt_tags1.fullmatch(base_old)
            if match:
                track = match.group(1)
                artist = match.group(2)
                title = match.group(3)

        if not match:
            match = pt_tags2.fullmatch(base_old)
            if match:
                track = match.group(1)
                artist = None
                title = match.group(2)

        if not match:
            track = None
            artist = None
            title = base_old

        for hash_new, file_new in items_new:
            if hash_old != hash_new:
                continue
            base_new = os.path.basename(file_new)

            tags.append((base_new, track, artist, title))
            found = True
            #don't break in case of repeats

        if not found:
            tags.append(('#?', track, artist, title))

    lines = [
        '# @ALBUM    ',
        '# $AUTOTRACK',
        '#',
        '',
    ]

    for file, track, artist, title in tags:
        if track:
            lines.append('##%%TRACK    %s' % (track))
        if artist:
            lines.append('# %%ARTIST   %s' % (artist))
        if title:
            lines.append('# %%TITLE    %s' % (title))
        if file:
            lines.append('%s' % (file))

    with open(dir_new+'/!tags.m3u', 'w') as f:
        f.write('\n'.join(lines))

main()
