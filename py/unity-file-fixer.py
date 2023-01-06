# joins chunked (file.ext-001, file.ext-002....) files and changes file.ext.bytes to file.ext
import glob, os, re

RENAME = False #don't rename by default since this script isn't very tested overall

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
        if RENAME:
            os.rename(file, base1)
        else:
            with open(file, 'rb') as fi, open(base1, 'wb') as fo:
                fo.write(fi.read())
            
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
