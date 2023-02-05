# Translate feelplus packed strings
# Derived from examples at https://pastebin.com/UkfBaSga
#  (original by hcs, minor mod by bnnm)

import struct

# Unknown chars shown as "{n}"
charset1 = ['{%s}'%(i,) for i in range(40)]

for i in range(10):
    charset1[i + 1] = str(i)

for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    charset1[11 + i] = c

#charset1[0] = ';'
charset1[37] = '_'
charset1[38] = '.'
charset1[39] = '/'

def unpack(words, char_count, has_size):
    unpack_all = False
    done = False
    max_words = None
    for idx, v in enumerate(words):
        # .fdi names encodes name size in first value (not always null-terminated)
        if max_words is not None and idx > max_words:
            break

        # for testing .fpi that has a long list of names
        if done:
            if not unpack_all:
                return
            done = False
            yield 0

        x = v % char_count
        v = (v - x) // char_count
        if x == 0:
            done = True
            continue
        
        if has_size and max_words is None:
            max_words = x + 1
        else:
            yield x

        y = v % char_count
        v = (v - y) // char_count
        if y == 0:
            done = True
            continue

        yield y

        z = v
        if z == 0 or z >= char_count: # 40 on bad data
            done = True
            continue
        yield z

    if done and unpack_all: #last break
        yield 0
    return


def wget(codes, pos, big_endian = True):
    fmt = '>H' if big_endian else '<H'
    return struct.unpack_from(fmt, codes, pos)[0]

# decode
#
# skip_middle_repeat: Otherwise 9274e791 be96efee be96efee cd4a0000 decodes to
#                     BGM01_TITLE.TITLE.XWV
def decode(codes, charset = charset1, skip_middle_repeat = True, big_endian = True, has_size=False):
    if len(codes) % 2:
        codes += b'\x00'

    # drop repeated middle dword
    if skip_middle_repeat and len(codes) == 0x10 and codes[0x04:0x08] == codes[0x08:0x0C]:
        codes = codes[0x00:0x08] + codes[0x0C:0x10]

    # split into 16-bit words
    words = [wget(codes, pos, big_endian) for pos in range(0, len(codes), 2)]

    # make string
    return ''.join(charset[c] for c in unpack(words, len(charset), has_size))

def decode_str(hex_string, skip_middle_repeat = True, big_endian = True, has_size = False):
    # parse string as hex
    codes = bytes.fromhex(hex_string)

    return decode(codes, skip_middle_repeat = skip_middle_repeat, big_endian = big_endian, has_size=has_size)
    
def decode_file(file, offset, size, skip_middle_repeat = True, big_endian = True, has_size = False):
    with open(file, 'rb') as f:
        f.seek(offset)
        codes = f.read(size)
    return decode(codes, skip_middle_repeat=skip_middle_repeat, big_endian=big_endian, has_size=has_size)


# Moon Diver
print(decode_str("9274e791 be96efee be96efee cd4a0000"))

# Mind Jack
print(decode_str("b309b16d c02d4734 c02d4734 da870275"))
print(decode_str("be856373 31a0ebc9 31a0ebc9 8b4f69d7"))
print(decode_str("be856373 31a0ebc9 31a0ebc9 8b4f69d7", skip_middle_repeat = False))

# Lost Odyssey Demo
print(decode_str("62e96906 937cc8ef 937cc8ef 6a620000", big_endian = False))
print(decode_str("d5bab46c b6ba0f00 b6ba0f00 00000000", big_endian = False))

# Lost Odyssey .fpi
print(decode_str("B29F26A50E000000000000000000", big_endian = False, has_size=True))
#print(decode_file('LO.fpi', 0x55C90+0x15A7*2, 0x30, big_endian=False, has_size=True))
