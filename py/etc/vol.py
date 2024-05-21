# waybackward/engineblack's .wave (maybe others) to .vol
import zlib, struct, os, sys

def deflate_vol(file):
    with open(file,'rb') as f:
        data = f.read()
    file, ext = os.path.splitext(file)

    dec = zlib.decompress( data[0x10:], -15)

    with open(file + '.wave','wb') as f:
        f.write(dec)


def inflate_vol(file):
    with open(file,'rb') as f:
        data = f.read()
    file, ext = os.path.splitext(file)

    enc = zlib.compress(data, wbits=-15)

    with open(file + '.vol','wb') as f:
        hdr = struct.pack('<III', 0x00000101, len(enc), len(data))
        f.write(b'\x50\xF0\x77\xD1')
        f.write(hdr)
        f.write(enc)


def main():
    if len(sys.argv) == 1:
        print("missing files")

    for file in sys.argv[1:]:
        inflate_vol(file)


main()
