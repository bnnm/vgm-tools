# FSB5-KEYHELPER
#
# helps finding FSB5 keys, with some human intervention. Miniguide:
# - call: fsb5-keyhelper.py (file)
#   - should work with .fsb and .bank
#   - tool is kinda slow, use -o and -s flags with giant files
# - this should create (file).key
# - open .key with a hex editor
# - look for patterns to find the correct key
#   - key is typically smaller than 0x20 then repeats until file end
#   - the first 8 bytes in .key should be correct, then until 0x20 a few bytes will be ok too
#   - most files have parts with many 0s, which means keys should be seen multiple times in the file
#     (look for those first 8 bytes and see repeated patters)
#   - keys are often in the exe or helper files too, so look for the first 8 chars in those files too
# - when you have a potential correct key: fsb5-keyhelper.py (file) -k (key)
# - this should create (file).dec.fsb
# - try to play it in vgsmtream; if it doesn't play tweak the key 
#   - open the .fsb with hex and see obvious wrong values compared to an expected FSB5 structure (LE):
#     00: FSB5
#     04: version (1, rarely 0)
#     08: total subsongs
#     0c: headers size
#     10: name table size
#     14: data size
#     18: codec (often 0x0F=vorbis, also 0x02=pcm16; see vgmstream's fsb5.c)
#     1c: usually 0
#     20: flags?
#     24: hashes, data, etc
#
# For fsb3/4 keys try guessfsb:
# - https://hcs64.com/files/guessfsb03.zip
# - https://hcs64.com/files/guessfsb04beta.zip
# (FSB5 was introduced in ~2009, but FSB4 is common until ~2016)


import sys, argparse, struct


class Cli(object):

    def _parse(self):
        description = (
            "fsb decryption key helper"
        )
        epilog = (
            "examples:\n"
            "  %(prog)s *.fsb\n"
            "  - does nothing (needs at least one filter)\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument('file', help="Files to process (wildcards work)")
        p.add_argument('-o',   dest='offset', help="start offset", type=lambda x: int(x,0))
        p.add_argument('-t',   dest='type', help="fsb type: 4/5", default='5')
        p.add_argument('-k',   dest='key', help="decryption key")
        p.add_argument('-s',   dest='size', help="decryption size")
        
        args = p.parse_args()
        if args.size:
            args.size = int(args.size, base=0)
        return args

    def start(self):
        args = self._parse()
        if not args.file:
            return
        Decryptor(args).start()


class Decryptor(object):
    REVERSE_BITS_TABLE = [
          #00   01   02   03   04   05   06   07   08   09   0A   0B   0C   0D   0E   0F
          0x00,0x80,0x40,0xC0,0x20,0xA0,0x60,0xE0,0x10,0x90,0x50,0xD0,0x30,0xB0,0x70,0xF0, #00
          0x08,0x88,0x48,0xC8,0x28,0xA8,0x68,0xE8,0x18,0x98,0x58,0xD8,0x38,0xB8,0x78,0xF8, #10
          0x04,0x84,0x44,0xC4,0x24,0xA4,0x64,0xE4,0x14,0x94,0x54,0xD4,0x34,0xB4,0x74,0xF4, #20
          0x0C,0x8C,0x4C,0xCC,0x2C,0xAC,0x6C,0xEC,0x1C,0x9C,0x5C,0xDC,0x3C,0xBC,0x7C,0xFC, #30
          0x02,0x82,0x42,0xC2,0x22,0xA2,0x62,0xE2,0x12,0x92,0x52,0xD2,0x32,0xB2,0x72,0xF2, #40
          0x0A,0x8A,0x4A,0xCA,0x2A,0xAA,0x6A,0xEA,0x1A,0x9A,0x5A,0xDA,0x3A,0xBA,0x7A,0xFA, #50
          0x06,0x86,0x46,0xC6,0x26,0xA6,0x66,0xE6,0x16,0x96,0x56,0xD6,0x36,0xB6,0x76,0xF6, #60
          0x0E,0x8E,0x4E,0xCE,0x2E,0xAE,0x6E,0xEE,0x1E,0x9E,0x5E,0xDE,0x3E,0xBE,0x7E,0xFE, #70
          0x01,0x81,0x41,0xC1,0x21,0xA1,0x61,0xE1,0x11,0x91,0x51,0xD1,0x31,0xB1,0x71,0xF1, #80
          0x09,0x89,0x49,0xC9,0x29,0xA9,0x69,0xE9,0x19,0x99,0x59,0xD9,0x39,0xB9,0x79,0xF9, #90
          0x05,0x85,0x45,0xC5,0x25,0xA5,0x65,0xE5,0x15,0x95,0x55,0xD5,0x35,0xB5,0x75,0xF5, #A0
          0x0D,0x8D,0x4D,0xCD,0x2D,0xAD,0x6D,0xED,0x1D,0x9D,0x5D,0xDD,0x3D,0xBD,0x7D,0xFD, #B0
          0x03,0x83,0x43,0xC3,0x23,0xA3,0x63,0xE3,0x13,0x93,0x53,0xD3,0x33,0xB3,0x73,0xF3, #C0
          0x0B,0x8B,0x4B,0xCB,0x2B,0xAB,0x6B,0xEB,0x1B,0x9B,0x5B,0xDB,0x3B,0xBB,0x7B,0xFB, #D0
          0x07,0x87,0x47,0xC7,0x27,0xA7,0x67,0xE7,0x17,0x97,0x57,0xD7,0x37,0xB7,0x77,0xF7, #E0
          0x0F,0x8F,0x4F,0xCF,0x2F,0xAF,0x6F,0xEF,0x1F,0x9F,0x5F,0xDF,0x3F,0xBF,0x7F,0xFF  #F0
    ]


    def __init__(self, args):
        self._args = args

    def _find_fsb(self, data):
        # abridged, see fsb_fev.c
        index = data.find(b'SNDH')
        if index <= 0:
            return None

        chunk_size, version, offset, size = struct.unpack_from("<IIII", data, index + 0x04)
        if chunk_size != 0x0c:
            return None

        return (offset, size)

    def _read_data(self):
        with open(self._args.file, 'rb') as f:
            if self._args.offset:
                f.seek(self._args.offset)

            if self._args.size:
                data = f.read(self._args.size)
            else:
                data = f.read()

        if not self._args.offset and not self._args.size and data[0:4] == b'RIFF':
            info = self._find_fsb(data)
            if not info:
                return None
            offset, size = info
            if offset and size:
                print("FSB in bank %x + %x" % (offset, size))
                data = data[offset : offset + size]
        
        return data

    def start(self):
        data = self._read_data()
        if not data:
            print("fsb not found, must pass offset")
            return

        if self._args.key:
            self.decrypt(data)
        else:
            self.reverse(data)
            
    def decrypt(self, data):
        data = bytearray(data)

        key = bytes(self._args.key,'UTF-8')
        keypos = 0
        for i in range(len(data)):
            if keypos >= len(key):
                keypos = 0
            xor = key[keypos]
            keypos += 1

            val = data[i]
            
            val = self.REVERSE_BITS_TABLE[val]
            val = val ^ xor
        
            data[i] = val

        with open(self._args.file + '.dec.fsb', 'wb') as f:
            f.write(data)

    def reverse(self, data):

        # guess FSB
        if self._args.type != '5':
            print("can't reverse FSB4 (use guessfsb.exe)")
            return

        self._data = data
        keysize = len(self._data)

        # detect key based on FSB 
        k = bytearray(keysize)
        # header
        k[0x00] = self._find(0x00, ord('F'))
        k[0x01] = self._find(0x01, ord('S'))
        k[0x02] = self._find(0x02, ord('B'))
        k[0x03] = self._find(0x03, ord('5'))

        # version (almost always 1)
        k[0x04] = self._find(0x04, 0x01)
        k[0x05] = self._find(0x05, 0x00)
        k[0x06] = self._find(0x06, 0x00)
        k[0x07] = self._find(0x07, 0x00)

        # total subsongs
        k[0x08] = self._find(0x08, 0x00)
        k[0x09] = self._find(0x09, 0x00)
        k[0x0a] = self._find(0x0a, 0x00)
        k[0x0b] = self._find(0x0b, 0x00)

        # sample header size
        k[0x0c] = self._find(0x0c, 0x00)
        k[0x0d] = self._find(0x0d, 0x00)
        k[0x0e] = self._find(0x0e, 0x00)
        k[0x0f] = self._find(0x0f, 0x00)

        # name table size
        k[0x10] = self._find(0x10, 0x00)
        k[0x11] = self._find(0x11, 0x00)
        k[0x12] = self._find(0x12, 0x00)
        k[0x13] = self._find(0x13, 0x00)

        # sample data size
        k[0x14] = self._find(0x14, 0x00)
        k[0x15] = self._find(0x15, 0x00)
        k[0x16] = self._find(0x16, 0x00)
        k[0x17] = self._find(0x17, 0x00)

        # codec
        k[0x18] = self._find(0x18, 0x0F) #vorbis = most common
        k[0x19] = self._find(0x19, 0x00)
        k[0x1a] = self._find(0x1a, 0x00)
        k[0x1b] = self._find(0x1b, 0x00)

        # usually zero?
        k[0x1c] = self._find(0x1c, 0x00)
        k[0x1d] = self._find(0x1d, 0x00)
        k[0x1e] = self._find(0x1e, 0x00)
        k[0x1f] = self._find(0x1f, 0x00)

        for i in range(0x20, keysize):
            k[i] = self._find(i, 0x00)
            if not k[i]: #?
                k[i] = 0

        with open(self._args.file + '.key', 'wb') as f:
            f.write(bytearray(k))


    def _find(self, pos, expected):
        val = self._data[pos]
        val = self.REVERSE_BITS_TABLE[val]
        for i in range(0x100):
            if val ^ i == expected:
                return i
        return None

if __name__ == "__main__":
    Cli().start()
