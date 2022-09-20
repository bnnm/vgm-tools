# renames VGMToolbox's output hex filenames to int 
# may have some issues
import os, sys

#mode = 'p'

rootdir = '.'

for filename in os.listdir(rootdir):

    basename, ext = os.path.splitext(filename)

    if ext in ['.py']:
        continue
    if len(basename) < 8:
        continue
    
    
    start = basename[:-8]
    str_hex = basename[-8:]

    num_dec = int(str_hex, 16)
    str_dec = str(num_dec).zfill(8)

    #if mode == 'p':
    #    new_filename = match.group(1) + "." + match.group(5)
    #else:
    # double __ to avoid clashing with not-yet-renamed files
    new_filename = start + "_" + str_dec + ext
    print(new_filename)

    if os.path.exists(new_filename)==True:
        print("Error: existing file" + new_filename)
        sys.exit(0)
    os.rename(filename, new_filename)
