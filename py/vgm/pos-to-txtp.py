# .pos to .txtp

import os, glob, struct

### CONFIG

bgm_dir = ''

#####

extensions = [
    '.wav', '.lwav', '.ogg', '.logg', '.at3', 'at9', '.aac', '.laac', '.vgmstream',
    '.WAV', '.LWAV', '.OGG', '.LOGG', '.AT3', 'AT9', '.AAC', '.LAAC', '.VGMSTREAM',
]


if bgm_dir and not bgm_dir.endswith('/'):
    bgm_dir = bgm_dir + '/'


files = glob.glob('*.pos')

for file in files:
    #print(file)
    
    if file.endswith('.pos'):
        posext = '.pos'
    elif file.endswith('.POS'):
        posext = '.POS'
    else:
        print("unknown .pos")
        break

    filename = None
    ext = None
    for extension in extensions:
        # name.xxx + name.pos
        origname = file.replace(posext, extension)
        if os.path.exists(origname):
            filename = origname
            ext = extension
            break

        # name.xxx + name.xxx.pos
        origname = file.replace(posext, '')
        if origname.endswith(extension) and os.path.exists(origname):
            filename = origname
            ext = extension
            break
    
    if not filename or not ext:
        print("original name not found for " + file)
        continue

    with open(file, 'rb') as fi:
        data = fi.read(0x08)

    lstart, lend = struct.unpack('<II', data)

    basename = os.path.basename(filename)

    txtpname = filename.replace(ext, '.txtp')
    if lend:
        txtpline = '%s%s #I %i %i' % (bgm_dir, basename, lstart, lend)
    elif lstart:
        txtpline = '%s%s #I %i' % (bgm_dir, basename, lstart)
    else:
        txtpline = '%s%s' % (bgm_dir, basename)
       
    #print("*output", txtpname, txtpline)
    with open(txtpname, 'w', encoding='utf-8') as fo:
        fo.write(txtpline)
