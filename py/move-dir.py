# moves certain files to dirs
# probably can be achieved with CMD but whatevs

import glob
import os

move = '/**/*.fsb'

dirs = glob.glob("*")
outdir = "_moved/"

for dir in dirs:
    print(dir)
    if not os.path.isdir(dir):
        continue
    if dir.startswith('_'):
        continue

    subfiles = glob.glob(dir + move, recursive=True)
    if not subfiles:
        continue

    
    try:
        os.mkdir(outdir)
    except OSError:
        pass
    os.rename(dir, outdir+dir)
