# dumb renamer of files that removes parcial strings, since it was kind of annoying to do via CMD

import glob, os, re

exts = [
    '**/*.zip',
]
replaces = [
    ('xxxx', ''),
]


files = []
for ext in exts:
    files.extend( glob.glob(ext, recursive=True) )
files.sort()


for file in files:
    try:
        outfile = file
        for r_in, r_out in replaces:
            outfile = outfile.replace(r_in, r_out)
        os.rename(file, outfile)
    except:
        print("can't rename", file)
