import glob, struct

def get_zstring(data, pos):
    end = pos
    while True:
        if data[end] == 0:
            break
        end += 1
    return data[pos:end]

def parse_bxm(filename, lines):
    with open(filename, 'rb') as f:
        data = f.read()

    if data[0:4] != b'BXM\x00' and data[0:4] != b'XML\x00' :
        return
    pos = 0x04

    #print("parsing", filename)

    version, files1, files2, strings_size = struct.unpack_from('>IHHI', data, pos)
    pos += 0x0c

    if version != 0:
        raise ValueError("unknown version")

    # unknown binary xml format for only need the strings (in shift jis so write as binary)

    pos = len(data) - strings_size
    #lines = []
    while pos < len(data):
        str = get_zstring(data, pos)
        pos += len(str)
        pos += 1 #null

        lines.append(str)

    #outname = filename + '.txt'
    #with open(outname, 'wb') as f:
    #    f.write(b'\n'.join(lines))

lines = []    
files = glob.glob('*.bxm')
for file in files:
    parse_bxm(file, lines)


outname = '_bxm.txt'
with open(outname, 'wb') as f:
    f.write(b'\n'.join(lines))
