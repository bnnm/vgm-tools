# Falcom table looper by bnnm
# v1: initial release
# v2: support for decompressed .tbb (use Falcom Decompress v2.py first)

import os
import struct

#config
bgm_subpath = 'bgm/'
bgm_ignore_dummy = True
bgm_extensions = [
    '.at3', #psp
    '.at9', #vita
    '.aac', #3ds
    #'.dec', #pc
    #'.de2', #pc
    #'.ogg', #pc?
]

# Ys 3 (PSP) .txt
def extract_elem_bgmtbl_y3(line):
    items = line.split()

    filename = items[0]
    lstart = items[1]
    lend = items[2]
    
    if filename == 'y3bg22_':
        return None
    
    try:
        loop_start = int(lstart)
    except:
        loop_start = 0

    try:
        loop_end = loop_start + int(lend)
    except:
        loop_end = 0
    loop = loop_end > 0

    elem = {
        'title': None,
        'filename': filename,
        'loop': loop,
        'loop_start': loop_start,
        'loop_end': loop_end,
    }
    return elem

# Brandish (PSP) .txt [loop length]
# The Legend of Heroes: Sora no Kiseki 1-3 .txt [loop length]
# The Legend of Heroes: Sora no Kiseki Material Collection .txt [no loops]
# Zwei (PSP) .txt [loop end]
# Ys Seven (PSP) .tbl [loop end]
# Ys vs. Sora no Kiseki (PSP) .tbl [loop end]
# Nayuta no Kiseki (PSP) .tbl [loop end]
def extract_elem_bgmtbl_std(line, has_comment, table):
    items = line.split()

    #'table': items[0]
    title = items[1]
    filename = items[2]
    loop = items[3]
    lstart = items[4]
    lend = items[5]

    # games define either loop start + length or loop start + end:
    # - games that use .txt use loop length, except Zwei
    # - Brandish has no comments, others have a "//tbl"
    # - Zwei writes "LoopEnd" in //tbl, but SnK1/1 incorrectly writes "LoopEnd" (SnK3 writes "Length")
    # - SnK always uses names in edXXXX format, others games aren't so fixed
    # - BGM_Nothing + ed6999 often exists for other games
    # detect loops length based on all that
    if table.endswith('.tbl'):
        is_loop_length = False #Ys7+
    else:
        if not has_comment:
            is_loop_length = True #Brandish
        elif title != 'BGM_Nothing' and filename.startswith('ed'):
            is_loop_length = True #SnK
        else:
            is_loop_length = False #Zwei

    loop = loop and loop.isdigit() and int(loop)

    try:
        loop_start = int(lstart)
    except:
        loop_start = 0

    try:
        if is_loop_length:
            loop_end = loop_start + int(lend)
        else:
            loop_end = int(lend)
    except:
        loop_end = 0

    elem = {
        'title': title,
        'filename': filename,
        'loop': loop,
        'loop_start': loop_start,
        'loop_end': loop_end,
    }
    return elem

def extract_bgmtbl(table):
    elems = []

    # mostly shift-jis but sometimes there are others chars?
    with open(table, 'r', encoding='shift-jis', errors='ignore') as infile:
    
        has_comment = False
        for line in infile:
            if line.startswith('//tbl'):
                has_comment = True
                continue

            elem = None
            
            if line.startswith('bgmtbl'):
                elem = extract_elem_bgmtbl_std(line, has_comment, table)
            elif line.startswith('y3bg'):
                elem = extract_elem_bgmtbl_y3(line)

            if not elem:
                continue
            elems.append(elem)
    return elems

# Gurumin (PSP) .map
def extract_map(table):
    elems = []

    # mostly shift-jis but sometimes there are others chars?
    with open(table, 'r', encoding='shift-jis', errors='ignore') as infile:
        reading = False
        for line in infile:
            if line.startswith('#EndBGMTable'):
                break
            if line.startswith('#BGMTable'):
                reading = True
                continue
            if not reading:
                continue

            if line.startswith('//ID'):
                continue
                
            items = line.split()
            if not items:
                continue
            id = items[0]
            name = items[1]
            lstart = items[3]
            lend = items[4]

            if name == 'bgm01' and id.startswith('//'):
                continue

            try:
                loop_start = int(lstart)
            except:
                loop_start = 0

            try:
                loop_end = int(lend)
            except:
                loop_end = 0

            loop = loop_end > 0 and loop_end != 10000000 and loop_end != 99999999

            elem = {
                'title': name.upper(),
                'filename': name.lower(),
                'loop': loop,
                'loop_start': loop_start,
                'loop_end': loop_end,
            }
            
            elems.append(elem)
    return elems

# Vantage Master Portable (PSP) .bin
def extract_boot(table):
    elems = []
    with open(table, 'rb') as infile:
        infile.seek(0x00173CD0)
        files = 42
        
        for i in range(0, files):
            data = infile.read(0x18)
            id, name, loop, lstart,lend = struct.unpack("<H12sHii", data)

            name = name.decode("utf-8").strip('\x00')
            if not name:
                continue

            elem = {
                'title': None,
                'filename': name,
                'loop': loop,
                'loop_start': lstart,
                'loop_end': lend,
            }
            elems.append(elem)

    return elems

# The Legend of Heroes: Zero no Kiseki (PSP)
# The Legend of Heroes: Ao no Kiseki (PSP)
def extract__dt(table):
    elems = []
    with open(table, 'rb') as infile:
        infile.seek(0, os.SEEK_END)
        size = infile.tell()
        infile.seek(0)

        files = size // 0x10

        for i in range(0, files):
            data = infile.read(0x10)
            lstart,lend,number,id,loop = struct.unpack("<iiIHH", data)
            
            name = "ed%04i" % (number)
            if not name:
                continue

            elem = {
                'title': None,
                'filename': name,
                'loop': loop,
                'loop_start': lstart,
                'loop_end': lstart + lend,
            }
            elems.append(elem)

    return elems

# Ys: Memories of Celceta (Vita)
# (probably others that have .tbb, but those have companion .tbl)
def extract_tbbdec(table):
    elems = []
    with open(table, 'rb') as infile:
        infile.seek(0, os.SEEK_END)
        size = infile.tell()
        infile.seek(0)

        files = size // 0x18

        for i in range(0, files):
            data = infile.read(0x18)
            lstart, name, id, loop, lend = struct.unpack("<i12sHHi", data)
            
            name = name.decode("utf-8").strip('\x00')
            if not name:
                continue

            elem = {
                'title': None,
                'filename': name,
                'loop': loop,
                'loop_start': lstart,
                'loop_end': lend,
            }
            elems.append(elem)

    return elems

#---

def extract_elems():
    table = 'bgmtbl.txt'
    if os.path.exists(table):
        return extract_bgmtbl(table)

    table = 'bgmtbl.tbl'
    if os.path.exists(table):
        return extract_bgmtbl(table)

    table = 'map.txt'
    if os.path.exists(table):
        return extract_map(table)

    table = 'BOOT.BIN'
    if os.path.exists(table):
        return extract_boot(table)

    table = 't_bgm._dt'
    if os.path.exists(table):
        return extract__dt(table)

    table = 'bgmtbl.tbbdec'
    if os.path.exists(table):
        return extract_tbbdec(table)

    return None

def main():
    elems = extract_elems()
    if not elems:
        return

    for elem in elems:
        title = elem['title']
        filename = elem['filename']
        loop = elem['loop']
        loop_start = elem['loop_start']
        loop_end = elem['loop_end']

        if not title:
            title = filename

        if not filename:
            raise ValueError("unknown filename")

        outname =  title + '.txtp'

        inname = None
        for bgm_extension in bgm_extensions:
            path_test = "%s%s%s" % (bgm_subpath, filename, bgm_extension)
            if os.path.exists(path_test):
                inname = path_test
                break

        if not inname and not bgm_ignore_dummy:
            inname = "%s%s" % (bgm_subpath, filename)

        if not inname:
            print("ignored dummy: %s (%s)" % (filename, outname))
            continue

        text = ''
        if loop:
            text += '%s #I %i %i' % (inname, loop_start, loop_end)
        else:
            text += '%s' % (inname)

        with open(outname, 'w', encoding='utf8') as outfile:
            outfile.write(text)


main()
