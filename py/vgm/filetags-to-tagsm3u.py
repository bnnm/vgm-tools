# makes !tags.m3u from "tagged" (renamed) files
# - put renamed files in "RENAMED" dir
# - put original names in "ORIGINAL" dir
# - run
# By default reads tags like "(artist) - (title)", change only_name if needed

import glob, hashlib, re, os

force_title = False # read "(title).ext", or "(artist) - (title).ext"
order_by_title = False # order results by renamed title rather than original filename
order_by_renamed = True # order results by renamed file rather than original filename

use_size = False #set to true to find files by approximate sizes
size_threshold = 0x100

write_track = False
write_artist = True

dir_ren = 'RENAMED'
dir_ori = 'ORIGINAL'
chunk = 0x10000


pt_tags1 = re.compile(r"([0-9][A-Za-z0-9]*)[ ]+[-]*[ ]*([A-Za-z0-9!@$%&()., '\-]+)[ ]+[-][ ]+(.+)")
pt_tags2 = re.compile(r"([0-9][A-Za-z0-9]*)[ ]+(.+)")

ignore_exts = ['.txt', '.m3u', '.zip', '.7z', '.bms']

def get_hash(file):
    if use_size:
        return os.path.getsize(file)

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
    items_ren = get_items(dir_ren + '/*.*')
    items_ori = get_items(dir_ori + '/*.*')

    tags = []
    for hash_ren, file_ren in items_ren:
        found = False

        base_ren = os.path.basename(file_ren)
        base_ren = os.path.splitext(base_ren)[0]

        match = None

        if not match:
            match = pt_tags1.fullmatch(base_ren)
            if match:
                track = match.group(1)
                artist = match.group(2)
                title = match.group(3)

        if not match:
            match = pt_tags2.fullmatch(base_ren)
            if match:
                track = match.group(1)
                artist = None
                title = match.group(2)

        if not match or force_title:
            track = None
            artist = None
            title = base_ren

        # find file
        for hash_ori, file_ori in items_ori:
            if use_size:
                if not (hash_ren <= hash_ori and hash_ren + size_threshold >= hash_ori):
                    continue
            else:
                if hash_ren != hash_ori:
                    continue
            base_new = os.path.basename(file_ori)

            tags.append((base_new, track, artist, title, base_ren))
            found = True
            #don't break in case of repeats

        if not found:
            tags.append(('#?', track, artist, title, base_ren))


    if order_by_renamed:
        tags.sort(key=lambda item: item[4])
    elif order_by_title:
        tags.sort(key=lambda item: item[3])
    else:
        tags.sort(key=lambda item: item[0])

    lines = []
    artists = []
    for file, track, artist, title, renamed in tags:
        if track and write_track:
            lines.append('##%%TRACK    %s' % (track))

        if artist:
            if write_artist:
                lines.append('# %%ARTIST   %s' % (artist))
            elif artist not in artists:
                artists.append(artist)

        if title:
            lines.append('# %%TITLE    %s' % (title))

        if file:
            lines.append('%s' % (file))

    
    header = []
    header.append('# @ALBUM    ')
    if artists:
        header.append('# @ARTIST   %s' % (', '.join(artists)))
    header.append('# $AUTOTRACK')
    header.append('#')
    header.append('')
    header.append('')


    with open(dir_ori+'/!tags.m3u', 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(header))
        f.write('\n'.join(lines))

if __name__ == "__main__":
    main()
