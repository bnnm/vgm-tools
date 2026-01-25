# .sxd info printer (for debugging purposes)

import glob, struct


class SxdParser():

    def __init__(self, file, data):
        self.file = file
        self.data = data
        self.lines = []
        self._depth = 0
        self._pos = 0
        self._is_be = False
    
    def add(self, text):
        indent = self._depth * 2 * ' '
        if not text:
            indent = ''
        self.lines.append(f'{indent}{text}')
        return self

    def next(self):
        self._depth += 1
        return self
    
    def prev(self):
        self._depth -= 1
        return self

    #---

    def fourcc(self):
        val = self.data[self._pos:self._pos+4]
        self._pos += 4
        return val

    def _unpack(self, fmt, size):
        if self._is_be:
            endian = '>'
        else:
            endian = '<'
        fmt = endian + fmt
        val, = struct.unpack_from(fmt, self.data, self._pos)
        self._pos += size
        return val

    def f32(self):
        return self._unpack('f', 4)

    def u64(self):
        return self._unpack('Q', 8)

    def u32(self):
        return self._unpack('I', 4)

    def s32(self):
        return self._unpack('i', 4)

    def u16(self):
        return self._unpack('H', 2)

    def s16(self):
        return self._unpack('h', 2)

    def u8(self):
        return self._unpack('B', 1)

    def strz(self):
        for i in range(256):
            c = self.data[self._pos + i]
            if c == 0:
                break
        return self.data[self._pos : self._pos + i].decode('utf-8')

    def chunk(self, size):
        chunk = self.data[self._pos : self._pos + size]
        self._pos += size
        return chunk

    def skip(self, val):
        self._pos += val

    def pos(self, val=None):
        if val is not None:
            self._pos = val
        return self._pos

    #---

    def parse_base(self):
        dummy = self.u32()
        count = self.u32()

        self.add(f'dummy  {dummy:08x}')
        self.add(f'count  {count} ({count:04x})')
        return count

    #---

    def parse_tone_item(self, count, offset, totals):
        curr = self.pos()
        offset = curr - 0x04 + offset

        self.pos(offset)
        for i in range(count):
            offset = self.pos()

            type = self.u16()
            note = self.s16()
            ext_id = self.u32()
            note_min = self.u16()
            note_max = self.u16()

            if note < 0:
                ext_type = 'seqd'
            else:
                ext_type = 'wave'

            self.add(f'Item[{i:04}/{i+totals:04}]    @{offset:08x}   {type:04x}  {note}  {ext_type}={ext_id:04}  {note_min},{note_max}')

        self.add('').pos(curr)
        return i + 1

    def parse_tone_sub(self, count, offset, num):
        curr = self.pos()
        offset = curr - 0x04 + offset

        totals = 0
        self.pos(offset)
        for i in range(count):
            offset = self.pos()

            unknown = self.u32()
            value1 = self.u16()
            sub_min = self.u16()
            sub_max = self.u16()
            sub_count = self.u16()
            sub_offset = self.u32() #from this offset

            self.add(f'Sub[{i:04}]    @{offset:08x}   {unknown:08x}  {value1}  {sub_min},{sub_max}')
            self.next()
            done = self.parse_tone_item(sub_count, sub_offset, totals)
            totals += done
            self.prev()

        self.pos(curr)
        pass

    def parse_tone(self):
        count = self.parse_base()

        for i in range(count):
            curr = self.pos()
            #self.add(f'Tone[{i}]   @{curr:08x}').next()

            unknown = self.u32()
            sub_min = self.u16()
            sub_max = self.u16()
            sub_count = self.u32()
            sub_offset = self.u32() #from this offset

            self.add(f'Tone[{i}]   @{curr:08x}   {unknown:08x}  {sub_min},{sub_max}')
            self.next()
            self.parse_tone_sub(sub_count, sub_offset, i)
            self.prev()

        pass

    #---

    def parse_reqd_entry(self, offset):
        curr = self.pos()
        offset = curr - 0x04 + offset

        self.pos(offset)
        #...

        #00: flags 
        #02: type? (00=wave? 01=seqd?)
        #04: flags? (always 4000)
        #08: wave ID or ? id otherwise (seqd in ca00 as no other valid numbers exist)
        #if flag 1 or 3
        #00: name offset
        #04: always 08
        #06: 06 signals 2 extra 32b
        #08: flags

        self.pos(curr)
        pass

    def parse_reqd(self, chunk_offset, chunk_size):
        count = self.parse_base()

        for i in range(count):
            offset = self.pos()

            sub_offset = self.u32() #from this offset

            if True:
                if i < count - 1:
                    curr = self.pos()
                    next_offset = self.u32() + 0x04 #from this offset
                    self.pos(curr)
                else:
                    next_offset = (chunk_size - 0x08) - (offset - chunk_offset)
                size = next_offset - sub_offset

                curr = self.pos()
                self.pos(offset + sub_offset)
                chunk = self.chunk(size)
                chunk = ' '.join(chunk[i:i+4].hex() for i in range(0, size, 4))
                self.pos(curr)

            self.add(f'Reqd[{i:04}]    @{offset + sub_offset:08x}  data={chunk}').next()

            self.parse_reqd_entry(sub_offset)
            self.prev()

        pass

    #---

    def parse_name(self, type='reqd'):
        count = self.parse_base()

        for i in range(count):
            offset = self.pos()

            name_offset = self.u32() #from this offset
            hash = self.u32()
            reqd_id = self.u32() #some REQD entries have a name offset, that offset and this entry match correctly

            name_offset += offset

            curr = self.pos()
            self.pos(name_offset)
            name = self.strz()
            self.pos(curr)

            self.add(f'Name[{i:04}]    @{offset:08x}  {hash:08x}  {type}={reqd_id:04}  {name}')

        pass

    #---

    def parse_wave(self):
        count = self.parse_base()
        for i in range(count):
            offset = self.pos()

            sub_offset = self.u32()

            self.add(f'Wave[{i:04}]    @{offset:08x}  {offset + sub_offset:08x}')
        pass

    #---

    def parse_seqd_entry(self, i, offset):
        curr = self.pos()
        offset = curr - 0x04 + offset

        self.pos(offset)

        value1 = self.u32()
        value2 = self.f32() #todo?
        value3 = self.u32()
        entry_size = self.u32()
        sub_offset = self.u32() #from this offset

        curr = self.pos()
        self.pos(curr - 0x04 + sub_offset)
        chunk = self.chunk(entry_size)
        chunk = ' '.join(chunk[i:i+4].hex() for i in range(0, entry_size, 4))
        self.pos(curr)

        self.add(f'Seqd[{i:04}]    @{offset:08x}  {value1:08x}  {value2:.3f}  {value3:08x}  {entry_size:08x}  {offset + 0x10 + sub_offset:08x}  data={chunk}')

        self.pos(curr)
        pass

    def parse_seqd(self):
        dummy = self.u32()
        count = self.u32()

        self.add(f'dummy  {dummy:08x}')
        self.add(f'count  {count} ({count:04x})')

        for i in range(count):
            offset = self.pos()
            #self.add(f'Tone[{i}]   @{curr:08x}').next()
            sub_offset = self.u32() #from this offset

            self.parse_seqd_entry(i, sub_offset)

        pass

    #---

    def parse_lvar(self):
        dummy = self.u32()
        count = self.u32()

        self.add(f'dummy  {dummy:08x}')
        self.add(f'count  {count}')

        for i in range(count):
            offset = self.pos()

            value1 = self.u32()
            value2 = self.u32()
            value3 = self.u32()
            value4 = self.u32()
            value5 = self.u32()
            value6 = self.u32()
            min = self.f32()
            max = self.f32()
            
            self.add(f'Lvar[{i:04}]    @{offset:08x}  {value1:08x}  {value2:08x}  {value3:08x}  {value4:08x}  {value5:08x}  {value6:08x}  ({min:.3f}, {max:.3f})')

        pass

    #---


    def parse_lvrn(self):
        self.parse_name(type='lvar')

    def parse_rxdf(self):
        dummy = self.u32()
        count = self.u32()

        self.add(f'dummy  {dummy:08x}')
        self.add(f'count  {count} ({count:04x})')

        pass

    def parse_rxfn(self):
        self.parse_name(type='rxdf')

    #---

    def parse(self):
        self.add(f'{self.file}').next()

        id = self.fourcc();
        if   id == b'SXDF':
            self._is_be = False
        else:
            self.add(f'- not an AWC file')
            return

        self.add(id)
        version = self.u16()
        unknown = self.u16()
        sxd1_size = self.u32()
        sxd2_size = self.u32()
        self.skip(0x10) #hash
        self.skip(0x40) #hash

        self.add(f'version  {version:04x}')
        self.add(f'unknown  {unknown:04x}')
        self.add(f'sxd1_size  {sxd1_size:08x}')
        self.add(f'sxd2_size  {sxd2_size:08x}')
        self.add(f'hash')
        self.add(f'name')
        self.add('')

        offset = self.pos()
        while offset < sxd1_size:
            chunk_offset = self.pos()
            chunk_id    = self.fourcc()
            chunk_size  = self.u32()
            self.add(f"{chunk_id}").next()
            self.add(f"chunk_offset {chunk_offset:08x}")
            self.add(f"chunk_size   {chunk_size:08x}")

           #if chunk_id == b'TOOL':
           #    #rare, hash + pascal string: ps4-mksndxd
           #    self.parse_tool() 
            if chunk_id == b'TONE':
                self.parse_tone()
            if chunk_id == b'REQD':
                self.parse_reqd(chunk_offset, chunk_size)
            if chunk_id == b'NAME':
                self.parse_name()
            if chunk_id == b'WAVE':
                self.parse_wave()
            if chunk_id == b'SEQD':
                self.parse_seqd()
            if chunk_id == b'LVAR':
                self.parse_lvar()
            if chunk_id == b'LVRN':
                self.parse_lvrn()
            if chunk_id == b'RXFD':
                self.parse_rxdf()
            if chunk_id == b'RXFN':
                self.parse_rxfn()
           #if chunk_id == b'TRNS':
           #    self.parse_trns()
           #if chunk_id == b'DATA':
           #    self.parse_trns()

            self.prev().add('')

            offset += chunk_size + 0x08
            self.pos(offset)

        return


    def print(self):
        for line in self.lines:
            print(line)

    def save(self):
        outfile = self.file + '.txt'
        with open(outfile, 'w') as f:
            f.write('\n'.join(self.lines))
        self.lines = []

def main():
    files  = glob.glob('*.sxd1')
    files += glob.glob('*.sxd')
    for file in files:
        with open(file, 'rb') as f:
            data = f.read()
        sxd = SxdParser(file, data)
        sxd.parse()
        sxd.save()
    #awc.print()
main()
