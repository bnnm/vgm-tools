# dumb renamer of files that removes partial strings, since it was kind of annoying to do via CMD

import glob, os, re

exts = [
    '**/*.jpg',
    '**/*.png',
]
replaces = [
    ('^xxx_start.', ''), #file start
    ('xxx_end$', ''), #file end
    ('xxx', ''), #middle
]

nums = True
if nums: #zero pad
    for i in range(0, 999):
        replaces.append( ('^%i.' % i, '%03i.' % i) )

files = []
for ext in exts:
    files.extend( glob.glob(ext, recursive=True) )
files.sort()


for file in files:
    try:
        outfile = file

        for r_in, r_out in replaces:
            if r_in.startswith('^'):
                outdir = os.path.dirname(outfile)
                outbase = os.path.basename(outfile)
                r_in = r_in[1:]
                if outbase.startswith(r_in):
                    outfile = os.path.join(outdir, r_out + outbase[len(r_in):])
            elif r_in.endswith('$'):
                outbase, outext = os.path.splitext(outfile)
                r_in = r_in[0:-1]
                if outbase.endswith(r_in):
                    outfile = outbase[0:-len(r_in)] + r_out + outext
            else:
                outfile = outfile.replace(r_in, r_out)

        if file != outfile:
            #print(file)
            #print(outfile)
            os.rename(file, outfile)
    except:
        print("can't rename", file)
