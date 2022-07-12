# renames unity .bytes and joins chunked files
import glob, os, re


files = glob.glob('**/*.bytes', recursive=True)
files.sort()

re_end = re.compile('.+-[0-9][0-9][0-9]')

for file in files:
    #base = os.path.basename(file)
    base1, _ = os.path.splitext(file)
    base2, ext = os.path.splitext(base1)
    if not ext:
        continue

    if not re_end.match(base2):
        # removes bytes
        os.rename(file, base1)
    else:
        # joins file-xxx.(ext) to single file
        with open(file, 'rb') as f:
            data = f.read()
        if base2.endswith('-001'):
            type = 'wb'
        else:
            type = 'ab'
        base3 = base2[0: -4] + ext
        with open(base3, type) as f:
            f.write(data)
