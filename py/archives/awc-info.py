# rockstar .awc info printer (for debugging purposes)

import glob, struct

CODECS = {
    0x00: 'PCM',
    0x01: 'PCM',
    0x04: 'IMA',
    0x05: 'XMA2',
    0x07: 'MPEG',
    0x08: 'Vorbis',
    0x0C: 'DSP',
    0x0F: 'ATRAC9',
    0x10: 'DSP-streamed',
}

class AwcParser():

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

    def fourcc(self):
        val = self.data[self._pos:self._pos+4];
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

    def pos(self, val=None):
        if val is not None:
            self._pos = val
        return self._pos


    def parse_tag(self, type, offset, size, is_seek_samples):
        pos = self.pos() #save

        self.pos(offset) #save
        self.next()
        
        if   type == 0x55:
            self.add("Data")
        
        elif type == 0x48:
            self.add("MusicHeader").next()
        
            block_count = self.u32()
            block_chunk = self.u32()
            channels = self.u32()
            self.add("block_count: %i" % (block_count))
            self.add("block_chunk: 0x%08x" % (block_chunk))
            self.add("channels: %i" % (channels))
        
            self.next()
            for ch in range(channels):
                stream_id = self.u32()
                num_samples = self.u32()
                headroom = self.s16()
                sample_rate = self.u16()
                codec = self.u8()
                round_size_ = self.u8()
                unknown2 = self.s16()

                codec_info = CODECS.get(codec, '?')
                self.add("Channel %i" % (ch)).next()
                self.add("stream_id: %08x" % (stream_id))
                self.add("num_samples: %i" % (num_samples))
                self.add("headroom: %i" % (headroom))
                self.add("sample_rate: %i" % (sample_rate))
                self.add("codec: %02x [%s]" % (codec, codec_info))
                self.add("round_size_: %02x" % (round_size_))
                self.add("unknown2: %i" % (unknown2))
                self.prev()
            self.prev()
        
            self.prev()
        
        
        elif type == 0xFA:
            self.add("SfxHeader").next()
        
            num_samples = self.u32()
            unknown1 = self.s32() #usually -1
            sample_rate = self.u16()
            headroom = self.s16()
            unknown2 = self.u16() #low number (some max?)
            unknown3 = self.u16()

            unknown4 = self.u16()
            unknown5 = self.u8()
            codec = self.u8()

            codec_info = CODECS.get(codec, '?')
            self.add("num_samples: %i" % (num_samples))
            self.add("unknown: %i" % (unknown1))
            self.add("sample_rate: %i" % (sample_rate))
            self.add("headroom: %i" % (headroom))
            self.add("unknown: %i" % (unknown2))
            self.add("unknown: %i" % (unknown3))
            self.add("unknown: %i" % (unknown4))
            self.add("unknown: %i" % (unknown5))
            self.add("codec: %02x [%s]" % (codec, codec_info))

            if size > 0x14:
                unknown6 = self.u32()
                self.add("unknown: %x" % (unknown6))

            self.prev()
        
        
        elif type == 0x76:
            self.add("SfxHeaderVorbis").next()

            num_samples = self.u32()
            unknown1 = self.s32() #usually -1
            sample_rate = self.u16()
            headroom = self.s16()
            unknown2 = self.u16() #low number
            unknown3 = self.u16()

            unknown4 = self.u16()
            unknown5 = self.u32()
            unknown6 = self.s32()
            unknown7 = self.u16()
            codec = self.u8()
            unknown8 = self.u8()
            setup_size = self.u16()

            codec_info = CODECS.get(codec, '?')
            self.add("num_samples: %i" % (num_samples))
            self.add("unknown: %i" % (unknown1))
            self.add("sample_rate: %i" % (sample_rate))
            self.add("headroom: %i" % (headroom))
            self.add("unknown: %i" % (unknown2))
            self.add("unknown: %i" % (unknown3))
            self.add("unknown: %i" % (unknown4))
            self.add("unknown: %i" % (unknown5))
            self.add("unknown: %i" % (unknown6))
            self.add("unknown: %i" % (unknown7))
            self.add("codec: %02x [%s]" % (codec, codec_info))
            self.add("unknown: %i" % (unknown8))
            self.add("setup_size: %04x" % (setup_size))
            self.add("setup data")

            self.prev()

        elif type == 0x7F:
            self.add("VorbisSetupData")


        elif type == 0xA3:
            self.add("SeekTable").next()
            
            if is_seek_samples:
                blocks = size // 4
                for i in range(blocks):
                    samples = self.u32()
                    self.add("block %i sample start: %i" % (i, samples))
            else:
                frames = size // 2
                for i in range(frames):
                    samples = self.u16()
                    self.add("frame %x size: %x" % (i, samples))
            self.prev()


        elif type == 0xBD:
            self.add("Events").next()
            events = size // 0x10

            for i in range(events):
                type_hash = self.u32()
                parameter_hash = self.u32()
                timestamp = self.u32()
                flags = self.u32()

                self.add("Event %i" % (i)).next()
                self.add("type_hash: %08x" % (type_hash))
                self.add("parameter_hash: %08x" % (parameter_hash))
                self.add("timestamp: %i" % (timestamp))
                self.add("flags: 0x%08x" % (flags))
                self.prev()

            self.prev()
        
        elif type == 0x68:
            self.add("MidiData")
        
        elif type == 0x5C:
            self.add("animation/RSC info?")
        elif type == 0x36:
            self.add("hash-something?")
        elif type == 0x2b:
            self.add("events/sizes??")

        else:
            self.add("Unknown").next()
            self.pos(offset + size)
            self.prev()

        #skipped = size - (self.pos() - offset)
        #if skipped:
        #    self.add("(skipped: 0x%08x)" % (skipped))

        self.prev()
        self.pos(pos) #restore

    def parse(self):
        self.add(f'{self.file}').next()

        id = self.fourcc();
        if   id == b'ADAT':
            self._is_be = False
        elif id == b'TADA':
            self._is_be = True
        else:
            self.add(f'- not an AWC file')
            return

        self.add(id)
        flags = self.u32()
        entries = self.u32()
        head_size = self.u32()
        
        self.add('flags     %08x' % flags)
        self.add('entries   %u' % entries)
        self.add('head_size 0x%x' % head_size)
        self.add('')

        if flags & 0x00010000:
            self.add("- flag: TagPositionTable").next().next()

            for i in range(entries):
                unk = self.u16()
                self.add('%i' % unk)
            self.prev().prev()

        if flags & 0x00020000:
            self.add("- flag: unordered descryptors")

        if flags & 0x00040000: #GTA5, not seen in RDR
            self.add("- flag: multichannel flag?")

        if flags & 0x00080000: #GTA5 PC
            self.add("- flag: encrypted data")
        self.add('')

        stream_infos = [0] * entries

        self.add("StreamInfo").next()
        for i in range(entries):
            info_header = self.u32()
            tag_count = (info_header >> 29) & 0x7 #3b
            stream_id = (info_header >>  0) & 0x1FFFFFFF #29b
            stream_infos[i] = (stream_id, tag_count)
            self.add('Stream %08x: %i tags' % (stream_id, tag_count))
        self.prev().add('')

        self.add("TagInfo").next()
        for i in range(entries):
            stream_id, tag_count = stream_infos[i]
            self.add('Stream %04i: %08x' % (i,stream_id)).next()
            
            #just checking (stream_id == 0) is not incorrect, some streams non-0 stream have a block seektable + musicheader (in that order)
            is_seek_samples = True 
            tag_infos = []
            for _ in range(tag_count):
                tag_header = self.u64()
                tag_type   = ((tag_header >> 56) & 0xFF) # 8b
                tag_size   = ((tag_header >> 28) & 0x0FFFFFFF) # 28b
                tag_offset = ((tag_header >>  0) & 0x0FFFFFFF) # 28b
                tag_infos.append( (tag_type, tag_size, tag_offset) )
                if tag_type == 0x48 or tag_type == 0x76:
                    is_seek_samples = True
            
            for tag_type, tag_size, tag_offset in tag_infos:
                self.add('Tag 0x%02X: offset=%08x, size=%08x' % (tag_type,tag_offset,tag_size))

                self.next()
                self.parse_tag(tag_type, tag_offset, tag_size, is_seek_samples)
                self.prev().add('')


            self.prev().add('')

        self.prev().add('')


    def print(self):
        for line in self.lines:
            print(line)

    def save(self):
        outfile = self.file + '.txt'
        with open(outfile, 'w') as f:
            f.write('\n'.join(self.lines))
        self.lines = []

def main():
    files = glob.glob('*.awc')
    for file in files:
        with open(file, 'rb') as f:
            data = f.read()
        awc = AwcParser(file, data)
        awc.parse()
        awc.save()
    #awc.print()
main()