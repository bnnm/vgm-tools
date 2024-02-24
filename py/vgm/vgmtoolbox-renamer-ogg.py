# renames VGMToolbox's output ogg hex filenames to int 
import os, sys, glob

IS_DEBUG = False
ZEROFILL = 3
rootdir = '.'

files = glob.glob('*.ogg')
files.sort() #handles hex

nums = {}
for filename in files:
    if '[tmp' in filename:
        continue
    
    basename, ext = os.path.splitext(filename)

    # (blah)_0x(offset)_size
    pos = basename.rfind('_0x')
    if not pos or pos < 0:
        continue

    start = basename[0:pos]
    if start not in nums:
        nums[start] = 0
    
    num = nums[start]
    nums[start] += 1
    str_dec = str(num).zfill(ZEROFILL)

    new_filename = start + "_" + str_dec + ext
    print("%s > %s" % (filename, new_filename))


    if not IS_DEBUG:
        if os.path.exists(new_filename):
            raise ValueError("renamed file exists: " + new_filename)
        os.rename(filename, new_filename)
