# extracts uasset text for some versions
import glob, struct, os

lines = []

files = glob.glob('**/*.uasset', recursive='true')
for file in files:
    print(file)
    with open(file, 'rb') as f:
        head = f.read(0x04)
        if head != b'\x00\x00\x00\x00':
            continue
        f.seek(0)
        data = f.read()
    lines.append('* ' + file)

    item_count, = struct.unpack_from('<I', data, 0x08)
    item_count += 1

    pos = 0x3c + 0x08 * item_count
    values = struct.unpack_from(f'>{item_count}H', data, pos)

    pos += 0x02 * item_count
    for i in range(item_count):
        nsize = values[i]
        line = data[pos : pos + nsize]
        line = line.decode('utf-8')
        pos += nsize

        lines.append(line)

    lines.append('')

with open('ww.txt', 'w') as f:
    f.write('\n'.join(lines))
