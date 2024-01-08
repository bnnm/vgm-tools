# renames VGMToolbox's output hex filenames to int 
# may have some issues
import os, sys

IS_DEBUG1 = False
IS_DEBUG2 = False
ZEROFILL = 3
rootdir = '.'

for filename in os.listdir(rootdir):
    basename, ext = os.path.splitext(filename)

    if ext in ['.py','.7z','.zip']:
        continue
    if '[tmp' in filename:
        continue
    basename2, ext2 = os.path.splitext(basename)
    if ext2: #double ext
        basename = basename2
        ext = ext2 + ext

    pos = basename.rfind('_')
    if not pos or pos < 0:
        continue
    start = basename[0:pos]
    str_hex = basename[pos+1:]

    num_dec = int(str_hex, 16)
    str_dec = str(num_dec).zfill(ZEROFILL)

    new_filename = start + "_" + str_dec + ext
    print("%s > %s" % (filename, new_filename))

    # to avoid clashes with bgm_00a > bgm_010 if bgm_010 (bgm_016) already exists
    new_filename += '[tmp%08x]' % (num_dec)

    if not IS_DEBUG1:
        if os.path.exists(new_filename):
            raise ValueError("renamed file exists: " + new_filename)
        os.rename(filename, new_filename)

for filename in os.listdir(rootdir):
    basename, ext = os.path.splitext(filename)
    if ext in ['.py']:
        continue
    
    pos = filename.rfind('[tmp')
    if not pos or pos <= 0:
        continue

    new_filename = filename[0:pos]
    #print(new_filename)

    if not IS_DEBUG2:
        os.rename(filename, new_filename)
