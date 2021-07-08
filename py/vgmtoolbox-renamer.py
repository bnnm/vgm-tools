# renames VGMToolbox's output hex filenames to int 
# may have some issues

import re
import os
import sys

mode = 'p'

format = re.compile('(.*[^_])([_])([0-9A-Fa-f]{8})([\.])(.+)')
rootdir = '.'

for filename in os.listdir(rootdir):

    match = format.match(filename)
    if not match:
        continue

    #group0: full filename
    #group1: base name
    #group2: _
    #group3: hex number
    #group4: .
    #group5: extension

    str_hex = match.group(3)
    num_dec = int(str_hex, 16)
    str_dec = str(num_dec).zfill(8)

    if mode == 'p':
        new_filename = match.group(1) + "." + match.group(5)
    else:
        # double __ to avoid clashing with not-yet-renamed files
        new_filename = match.group(1) + "__" + str_dec + "." + match.group(5)

    if os.path.exists(new_filename)==True:
        print("Error: existing file" + new_filename)
        sys.exit(0)
    os.rename(filename, new_filename)

#raw_input('done')
