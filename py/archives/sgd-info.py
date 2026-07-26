# .sgd info printer (for debugging purposes)
# Info from: 
# - https://github.com/Nezogoku/sgd_extractor
# - https://github.com/Nenkai/010GameTemplates/blob/main/Sony/SGXD.bt

import glob, struct


class SgxdParser():

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

    def parse_rgnd_item(self, count, offset, totals):
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

    def parse_rgnd_sub(self, count, offset, num):
        self.pos(offset)
        for i in range(count):
            sub_offset = self.pos()

            flag = self.u32()
            name_offset = self.u32()
            rgnsiz = self.u32()
            
            if rgnsiz != 0x38:
                self.add(f'Sub[{i:04}]    @{sub_offset:08x}   {rgnsiz:08x}  {name_offset:08x}  {flag:08x} ???')
                sub_offset += rgnsiz
                self.pos(sub_offset)
            
            voice = self.u8()
            excl = self.u8()
            bnkmode = self.u8()
            bnkid = self.u8()

            unk1 = self.u32() #resv1
            effect = self.u32()

            notelow = self.u8()
            notehigh = self.u8()
            unk2 = self.u16()

            noteroot = self.u8()
            notetune = self.u8()
            notepitch = self.u16()

            vol0 = self.u16()
            vol1 = self.u16()
            gendry = self.u16()
            genwet = self.u16()

            env0 = self.u32()
            env1 = self.u32()

            vol = self.u8()
            pan = self.u8()
            bendlow = self.u8()
            bendhigh = self.u8()

            smpid = self.u32()

            self.add(f'RegionDefition[{i:04}]    @{sub_offset:08x}   {rgnsiz:08x}  {name_offset:08x}  {flag:08x}')

            self.next()
            self.add(f'voice={voice}, excl={excl}, bnkmode={bnkmode}, bnkid={bnkid}, unk1={unk1}, effect={effect}')
            self.add(f'notelow={notelow}, notehigh={notehigh}, unk2={unk2}, noteroot={noteroot}, notetune={notetune}, notepitch={notepitch}')
            self.add(f'vol0={vol0}, vol1={vol1}, gendry={gendry}, genwet={genwet}, env0={env0}, env1={env1}')
            self.add(f'vol={pan}, pan={pan}, bendlow={bendlow}, bendlow={bendlow}')
            self.add(f'smpid={smpid}')
            self.prev()

        pass

    # region definitions 
    def parse_rgnd(self):
        base_offset = self.pos()
        count = self.parse_base()

        regions = []
        for i in range(count):
            region_count = self.u32()
            region_offset = self.u32()
            regions.append((region_count, region_offset))


        for i in range(count):
            region_count, region_offset = regions[i]

            self.add(f'Region[{i}]   @{region_offset:08x}  count={region_count}')
            self.next()
            self.parse_rgnd_sub(region_count, region_offset, i)
            self.prev()

        pass

    #---
    
    NAME_TYPES = {
        0: 'STREAM', #wave stream
        1: 'NOTE',
        2: 'SEQUENCE',
        3: 'SAMPLE', #wave
        4: 'BUS SETUP',
        5: 'BUS EFFECT',
        6: 'CONFIG',
    }

    def parse_name(self, type='reqd'):
        count = self.parse_base()

        for i in range(count):
            offset = self.pos()

            reqsmp  = self.u16()    #Wave request ID
            reqseq  = self.u8()     #Sequence request ID
            type    = self.u8()     #Request type
            name_offset = self.u32() #

            curr = self.pos()
            self.pos(name_offset)
            name = self.strz()
            self.pos(curr)

            name_type = (type >> 4) & 0xFF
            name_desc = self.NAME_TYPES.get(name_type, '???')


            self.add(f'Name[{i:04}]    @{offset:08x}  reqsmp={reqsmp:04x}, reqseq={reqseq:02}, type={type:02x}-{name_desc:10}  {name}')

        pass

    #---

    def parse_wave(self):
        count = self.parse_base()
        for i in range(count):
            offset = self.pos()

            flags = self.u32()
            name = self.u32()
            codec = self.u8()
            chns = self.u8()
            numloop = self.u8()
            reserved = self.u8()
            smprate = self.u32()
            rate0 = self.u32() #BitRate
            rate1 = self.u32() #kbps in AC3?
            volleft = self.u16()
            volright = self.u16()
            looppos = self.u32() #loop start offset
            loopsmp = self.u32() #loop start sample
            loopbeg = self.u32() #loop end offset
            loopend = self.u32() #loop end sample
            bsize = self.u32()
            bstart = self.u32() #start data
            bend = self.u32() #end data
           
            size = 0x38

            self.add(f'Wave[{i:04}]    @{offset:08x}  {offset + size:08x}')

            self.next()
            self.add(f'flags={flags}, name={name}, codec={codec}, chns={chns}')
            self.add(f'numloop={numloop}, reserved={reserved}, smprate={smprate}, rate0={rate0}, rate1={rate1}')
            self.add(f'volleft={volleft}, volright={volright}, looppos={looppos:08x}, loopsmp={loopsmp}, looppos={loopbeg:08x}, loopsmp={loopend}')
            self.add(f'bsize={bsize:08x}, bstart={bstart:08x}, bend={bend:08x}')
            self.prev().add('')
            
            #offset += size
            #self.pos(offset)
        pass

    #---

    TAGS = {
        0xB0: 'SesqSubPlay',
        0xB1: 'SesqSubStop',
        0xB2: 'SesqSubStopRel',
        0xB3: 'SesqSubGetStatus',
        0xC0: 'SesqCtrl',
        0xC1: 'SesqAdsr',
        0xC2: 'SesqBendW',
        0xC3: 'SesqAdsrDirect',
        0xD0: 'SesqPlay',
        0xD1: 'SesqStop',
        0xD2: 'SesqStopRel',
        0xD3: 'GetPortStatus',
        0xD4: 'SesqPlayWave',
        0xD5: 'SesqPlayNoise',
        0xE0: 'sgxSndSetSysReg',
        0xE1: 'sgxSndSetSysReg_Add',
        0xE2: 'sgxSndSetSysReg_Minus',
        0xE3: 'sgxSndSetSysReg_Mul',
        0xE4: 'sgxSndSetSysReg_Div',
        0xE5: 'sgxSndSetSysReg_Mod',
        0xE6: 'sgxSndSetSysReg_And',
        0xE7: 'sgxSndSetSysReg_Or',
        0xE8: 'sgxSndSetSysReg_Xor',
        0xF0: 'Unk_0xF0',
        0xF1: 'Wait',
        0xF2: 'Jump',
        0xF3: 'LoopBegProc',
        0xF4: 'LoopEndProc',
        0xF5: 'JumpNotEqual',
        0xF6: 'Jump3',
        0xF7: 'JumpGreaterEqual',
        0xF8: 'JumpLesser',
        0xF9: 'sgxSndDoMarkerCallback',
        0xFA: 'SesqLoopBreak',
        0xFE: 'Print',
        0xFF: 'End',
    }

    def parse_seqd_body(self, fmt, cmd_size):
        if cmd_size == 0:
            return
        if fmt == 0x00:
            pos = self.pos()
            end = pos + cmd_size
            #while pos < end:
            type = self.u8()
            tag = self.TAGS.get(type, '???')
            self.add(f'tag={type:02x}-{tag}')

            cfg = self.u8()
            type = (cfg >> 4) & 0xF
            size = (cfg >> 0) & 0xF
            # PositiveBcd = 0, NegativeBcd = 1, Random = 2, SysReg = 3, Reg = 4, Unk = 5

            if type == 0x02: #random
                pass
            # f1 wait: time
            
            # b0 play: id, prog, note, volume
            
            # non-commands should be ignored?

        else:
            self.add(f'(unknown format)')

    def parse_seqd_entry(self, num, offset):
        if offset == 0:
            return
        curr = self.pos()

        self.pos(offset)

        flags = self.u32()
        name_offset = self.u32()
        fmt = self.u16() #0=sesq, 1=midi
        fiv = self.u16()
        vol_l = self.u16()
        vol_r = self.u16()
        cmd_size = self.u32()
        # body of cmd_size
        
        
        self.add(f'SeqdEntry[{num}]   @{offset:08x} no={name_offset:08x} fmt={fmt}, fiv={fmt}, sz={cmd_size:08x}')
        self.next()
        self.parse_seqd_body(fmt, cmd_size)
        self.prev().add('')
        self.pos(curr)

    def parse_seqd_group(self, num, offset):
        if offset == 0:
            return
        curr = self.pos()
        self.pos(offset)

        flags = self.u32()
        count = self.u32()
        self.add(f'SeqdGroup[{num}]   @{offset:08x}  {count}')
        self.next()

        for i in range(count):
            sub_offset = self.u32()
            self.parse_seqd_entry(i, sub_offset)

        self.prev().add('')
        self.pos(curr)

    def parse_seqd(self):
        count = self.parse_base()

        offsets = []
        for i in range(count):
            offset = self.u32()
            offsets.append(offset)
            
        for i in range(count):
            offset = offsets[i]
            self.parse_seqd_group(i, offset)

        pass

    #---

    def parse(self):
        self.add(f'{self.file}').next()

        id = self.fourcc();
        if   id == b'SGXD':
            self._is_be = False
        else:
            self.add(f'- not an SGXD file')
            return

        self.add(id)
        names_offset = self.u32()
        data_offset = self.u32()
        data_size = self.u32()

        self.add(f'names_offset {names_offset:04x}')
        self.add(f'data_offset  {data_offset:08x}')
        self.add(f'data_size    {data_size:08x}')
        self.add('')

        offset = self.pos()
        while offset < data_offset:
            chunk_offset = self.pos()
            chunk_id    = self.fourcc()
            chunk_size  = self.u32()
            self.add(f"{chunk_id}").next()
            self.add(f"chunk_offset {chunk_offset:08x}")
            self.add(f"chunk_size   {chunk_size:08x}")

            if chunk_id == b'RGND':
                self.parse_rgnd()
            if chunk_id == b'NAME':
                self.parse_name()
            if chunk_id == b'WAVE':
                self.parse_wave()
            if chunk_id == b'SEQD':
                self.parse_seqd()

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
    files  = glob.glob('*.sgh')
    files += glob.glob('*.sgd')
    for file in files:
        with open(file, 'rb') as f:
            data = f.read()
        item = SgxdParser(file, data)
        item.parse()
        item.save()
    #awc.print()
main()
