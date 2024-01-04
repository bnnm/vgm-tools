# DEMOFLEX: demuxes .moflex videos
# Usage: install python + run in some path with .moflex videos
#
# NOTES:
# - can't quite extract raw data from .moflex due to the way audio packets work
#   (like non-constant interleave, etc)
# - this creates slightly odd/invalid .moflex (since there are a bunch of unknown values)
#   that are slightly bloated (a bunch of blocks with header only andno packets)
#   - usable in ffmpeg and (eventually) vgmstream.
#   - should be possible to re-demux from already demuxed audio-only (files)
#     to fix those issues in the future
# - there is a type of moflex that can't be demuxed due to a bug (to be fixed)
#
#------------------------------------------------------------------------------
#
# info from:
# - https://github.com/Gericom/MobiclipDecoder
# - https://github.com/FFmpeg/FFmpeg
#
# TODO validate changes in sync info between blocks
# TODO improve code to copy 'data' to 'out'
# TODO check why PCM16 packets can be odd (0F97)
# TODO check flag for DSP/IMA packets with and without header hist
# TODO fix demux with movies with "unknown flag" (packet desync)
#
#
# format:
# - data is divided into blocks containing N packets (OggS style, pages > frames)
# - on new block peek 16b sync
#   - sync determines if block has header info/flags (keyframe?), or not (non-keyframe?)
# - header sync (4c32):
#   - header sets block's "streams", for various data types (video, audio, tables)
#   - repeated in multiple blocks, first one acts as file header
# - other value: not a sync (16b is part of other values)
# - read block's packet (stream id, some flags, packet size)
#   - keyframe blocks usually only contain 1-2 packets
#   - regular blocks usually contain N packets
# - repeat until block ends
# - block ends if either:
#   * read full block size set in sync header (common, always(?) 0x1000))
#   * found block end flag (less common)
#   * EOF (for last block)
# - keep reading blocks + packets until EOF
#
# ex: [block0: sync|packet0|...|packetN][block1: sync|packet1|...|packetN][...](EOF)
#
# audio packet format (after flags + size)
# - PCM16: straight data but sizes often are odd?
# - IMA: 
#   * some packes may have step + hist (per channel)
#     - usually smaller frames don't have it, but not always (ex. 0492=no, 41c=has)
#     - usually first frame of block don't have it, but not always
#   * ima data in subframes?
#     (frame_bytes - 4 * ch) / (128 * ch) * 256;
# - DSP: 
#   - half size per channel (ex. 0x504 > 0x282 L + 0x282 R)
#   per channel
#   00: coefs (only in keyframes?)
#   20: PS start + hist1 + hist2 (hist always null)
#   26: data until packet end
# - fastaudio: custom codec, not investivated

import glob, sys, os, argparse


class AudioInfo:
    CODEC_INFO = {
        0: 'FastAudio',     #v1/v2?
        1: 'Moflex-IMA',
        2: 'PCM16',       
       #3: ?
        4: 'DSP',
       #5: 'Vorbis?',
    }

    def __init__(self):
        self.stream_index = None
        self.codec = None
        self.sample_rate = None
        self.channels = None
        
    def info(self):
        line = "index = #%s\ncodec = %s\nchannels = %s\nsample_rate = %s"
        line = line % (self.stream_index, self.CODEC_INFO.get(self.codec, '???'), self.channels, self.sample_rate)
        return line


class Demoflex():
    HEADER_SYNC = 0x4c32

    def __init__(self, args, filename):
        self._args = args
        self._reader = Reader(filename)
        self._logger = Logger(args, self._reader)
        self._filename = filename

        # process info
        self._known_indexes = []
        self._audio_indexes = []
        self._audio_info = {} # index > audio
        
        # block state
        self.init_done = False #flag, first header inits the file
        self.subsync = 0
        self.timestamp = 0
        self.block_size = 0

    
    def parse_sync(self):
        r = self._reader
        log = self._logger
        data = r._data #todo

        # 4C32 = header, other = not a sync, handled in parse_block_flags
        self.sync = r.get_u16() #peek
        if self.sync != self.HEADER_SYNC:
            return

        self.subsync = r.get_u16(0x02) # unknown, but first blocks are always AAAB
        self.timestamp = r.get_u64(0x04) # timestamp (1...N)
        self.block_size = r.get_u16(0x0c) + 1

        log.debug("- head (sub=%04x, ts=%i)" % (self.subsync, self.timestamp))

        if not self.init_done or True:        
            self.out += data[r.offset + 0x00 : r.offset + 0x0e] #first sync
        r.skip(0x0e)

        max = r.offset + self.block_size
        while True:
            if r.offset > max:
                raise ValueError("bad size")

            current = r.savepos()

            # supposedly variable but only seen 1 byte
            tag = r.read_uv()
            size = r.read_uv()
            current2 = r.offset + size
            log.trace("  > tag %02x (%x)" % (tag, size))

            # decide if tag should be included
            # TODO: ffmpeg needs at least 1 video tag to work (MoLiveStreamTimeline can be skipped)
            include = True

            if self._args.full:
                include = True

            # handle tags
            if   tag == 0x00: #end signal
                stream_index = None
                include = True
                pass

            elif tag == 0x01 or tag == 0x03: #MoLiveStreamVideo, MoLiveStreamVideoWithLayout
                # video info
                stream_index = r.get_u8(0x00)
                # 01: codec (00: mobiclip)
                # 02: tb-den
                # 04: tb-num
                # 06: width
                # 08: height
                # 0a: x2 flags
                # 0c: x1 flags (tag 3 only)

            elif tag == 0x02: #MoLiveStreamAudio
                include = True
                audio_pos = r.savepos()
                stream_index = r.get_u8(0x00)
                if not self.init_done:
                    self._audio_indexes.append(stream_index)
                    
                    ai = AudioInfo()
                    ai.stream_index = stream_index
                    ai.codec = r.get_u8(0x01)
                    ai.sample_rate = r.get_u24(0x02) + 1
                    ai.channels = r.get_u8(0x05) + 1
                    self._audio_info[stream_index] = ai

                    log.warn(ai.info())

                if not self.init_done and self._args.raw:
                    temp = 0
                    self.raw += data[audio_pos : audio_pos + 0x06]
                    self.raw += temp.to_bytes(0x10 - 0x06, 'big')


            elif tag == 0x04: #MoLiveStreamTimeline
                # seek table:
                #  00 entries
                #  04 max id/number?
                #  08 max timestamp?
                #  0c ? (stream index?)
                #  per entry (size 0x18):
                #   00 id/number
                #   08 block timestamp
                #   10 block offset (always to a headered block)
                # timestamp format?
                #  ex. 1ED2C9 samples 2ch 32728 hz ~= 45.80s
                #       max ts = 0x029A4CEB = 43666667 = 43.666s?
                stream_index = r.get_u8(0x00)

            #0x100000://MoLiveChunkFoo?
            else:
                raise ValueError("unknown tag")

            if stream_index is not None and stream_index not in self._known_indexes:
                self._known_indexes.append(stream_index)

            if include:
                self.out += data[current : current2]

            r.skip(size)
            if tag == 0x00 or size == 0x00:
                break

        # use first packet as info
        if not self.init_done:
            self.init_done = True
            if not self._audio_indexes:
                log.warn("file has no audio")
        else:
            #TODO validate?
            return


    def parse_packet(self):
        log = self._logger
        r = self._reader
        data = r._data #todo
    
        log.debug("  new packet")

        r.init_br()

        # example: 0x6C8000000129C0
        # 01101100 10000000 00000000 00000000 00000001 00101001 11000000
        # 01 10 1 1 0 0 1 0000000000000000000000000000 0010010100111 000000
        # - read bits: 2 [1 + 0]
        # - read stream: 2 [10]
        # - read endframe flag = 1 [1]
        # - read bits2: 1 [1]
        # - read size2: 0 [0]
        # - unk flag: 0 [0]
        # - read bits3: 1 [1]
        # - read size3: 1 * 2 + 26
        # - read 13b packet size 4A7+1 10010100111

        current = r.savepos()

        bits = r.read_len()
        stream_index = r.read_value(bits)
        if stream_index not in self._known_indexes:
            raise ValueError("unknown stream %i" % (stream_index))

        endframe = r.read_bit()
        log.trace("  > bits=%i, stream=%i, endframe=%i" % (bits, stream_index, endframe))
        if endframe:
            # see:
            # https://github.com/Gericom/MobiclipDecoder/blob/c88b67d3cca93de03d286f67f01ee40da605f5ae/LibMobiclip/Containers/Moflex/MoLiveDemux.cs#L303
            # https://github.com/FFmpeg/FFmpeg/blob/59686eaf336a71f2e9297f1f2df4587ea9dc76a0/libavformat/moflex.c#L304
            
            bits = r.read_len()
            frame_type = r.read_value(bits)
            unk_flag = r.read_bit()

            # unknown counter:
            # - starts from zero, increases for audio and video (not all packets)
            # - resets after new header 
            # - in rare cases maybe slightly lower than previous counter within the same block 
            #   (ex. video 0x8235 > audio 7d00)
            # - may be > 32b?
            bits = r.read_len()
            unk_counter = r.read_value(2 * bits + 26)

            # may mean negative unk_counter, but not used in MobiclipDecoder?
            if unk_flag:
                log.debug("  > found unknown flag")

            log.trace("  > frame_type=%04i, unk_flag=%04i, unk_counter=%04x" % (frame_type, unk_flag, unk_counter))

        packet_size = r.read_value(13) + 1
        #if packet_size <= 1: #0x01 is possible
        #    raise ValueError("wrong size %x" % (packet_size))
        log.trace("  > pkt_size=%x" % (packet_size))

        data_start = r.savepos() #aligned
        r.skip(packet_size)

        # there are some remaining bits but not needed
        current2 = r.offset

        include = False
        if stream_index in self._audio_indexes:
            include = True #saves flags + packet data
            log.debug("  > aud_size=%x > %x + %x" % (current, data_start, packet_size))
            
            if self._args.raw:
                # funny padded/blocked pseudo format for testing
                padding = (packet_size + 0x04 + 0x04 + 0x04 + 0x04) % 0x10
                if padding:
                    padding = 0x10 - padding
                self.raw += b'MOFL'

                full_size = packet_size + 0x04 + 0x04 + 0x04 + 0x04 + padding
                self.raw += full_size.to_bytes(0x04, 'big')
                self.raw += (packet_size - 1).to_bytes(0x04, 'big')
                self.raw += stream_index.to_bytes(0x04, 'big')
                self.raw += data[data_start : current2]

                if padding:
                    self.raw += bytearray([0xff] * padding)

        if self._args.full:
            include = True

        if include:
            self.out += data[current : current2]

        if endframe:
            log.debug("  * packet end flag")
            return #still in block

        return

    def parse_block_flags(self):
        log = self._logger
        r = self._reader

        self.out += r.data(0x01)
        flags = r.read_u8()

        log.debug("- flags %02x = %s" % (flags, bin(flags)))

        FLAG_VariablePacketSize = 0x01 #affect padding?
        FLAG_PacketCounting = 0x02
        FLAG_SynchroCounter = 0xFC #counts from 0..64 but not always?
        if flags & FLAG_PacketCounting:
            self.out += r.data(0x02) #counter 0..FFFF?
            r.skip(0x2)

    def parse_block(self):
        log = self._logger
        r = self._reader

        log.debug("")
        log.debug("new block")
        current = r.savepos()
        out_cur = len(self.out)

        self.parse_sync()
        self.parse_block_flags()

        offset_max = current + self.block_size

        size_done = False
        packets = 0
        while True:
            # block ends (no more packets) on eof, max size reached, or end flag found
            if r.is_eof():
                break

            if r.offset == offset_max:
                log.debug("* block end size (0x%x)" % (self.block_size))
                size_done = True
                break
            if r.offset > offset_max:
                raise ValueError("read past block")

            if r.get_u8(0x00) == 0x00: #peek
                self.out += r.data(0x01)
                r.skip(0x1)
                log.debug("* block end flag")
                break

            self.parse_packet()
            packets += 1

        log.debug("* packets: %i" % (packets))

        # packets may end when reaching max capacity, but when demuxing audio
        # this doesn't happen as much and we need to set the end flag
        if size_done:
            out_cur2 = len(self.out)
            if (out_cur2 - out_cur) < self.block_size:
                self.out += bytearray([0]) #end flag

        return

    def demux(self):
        r = self._reader
        log = self._logger

        id = r.get_u32() #peek
        if id != 0x4C32AAAB:
           log.warn("not a .moflex file")
           return

        while True:
            if r.is_eof():
                return
            self.parse_block()

    def start(self):    
        log = self._logger
       
        log.warn("- parsing %s" % (self._filename))

        self.out = bytearray()
        self.raw = bytearray()
        self.demux()

        if len(self.out) <= 0 and len(self.raw) <= 0:
            return

        #for aix in self._audio_indexes:
        #    ai = self._audio_info.get(aix)
        #    if ai:
        #        print("-",self._filename)
        #        print(ai.info())

        basename = os.path.basename(self._filename)
        basename, ext = os.path.splitext(basename)

        
        
        is_write = True
        if self._args.info:
            is_write = False
        if not len(self.out) or not self._audio_indexes and not self._args.full:
            is_write = False
        
        if is_write:
            if self._args.full:
                type = '.full'
            else:
                type = '.audio'

            file_out = "%s%s%s" % (basename, type, ext)
            with open(file_out, 'wb') as f:
                f.write(self.out)

        if len(self.raw) and not self._args.info:
            type = '.audioraw'

            file_out = "%s%s%s" % (basename, type, ext)
            with open(file_out, 'wb') as f:
                f.write(self.raw)

        log.info("done")


class Logger:
    def __init__(self, args, r):
        self._args = args
        self._reader = r

    def _text(self, text, show_offset=False):
        if not text.strip():
            print("")
            return

        r = self._reader
        if not r or not show_offset:
            print("%s" % (text))
        elif r:
            print("[%06x] %s" % (r.offset, text))

    def warn(self, text):
        return self._text(text)

    def info(self, text):
        if not self._args.verbose_info and not self._args.verbose_debug and not self._args.verbose_trace:
            return
        return self._text(text)

    def debug(self, text):
        if not self._args.verbose_debug and not self._args.verbose_trace:
            return
        return self._text(text, show_offset=True)

    def trace(self, text):
        if not self._args.verbose_trace:
            return
        return self._text(text, show_offset=True)


class Reader:
    def __init__(self, file):
        self.offset = 0x00
        with open(file, 'rb') as f:
            self._data = f.read()

        self.init_br()
        
    def init_br(self):
        self.br_curr = 0
        self.br_mask = 0x00
        pass

    def data(self, size):
        return self._data[self.offset : self.offset + size]
        
    def skip(self, size):
        self.offset += size

    def savepos(self):
        return self.offset
    
    def is_eof(self):
        return self.offset >= len(self._data)

    def read_bit(self):
        if self.br_mask == 0:
            self.br_curr = self._data[self.offset]
            self.offset += 1
            self.br_mask = 0x80
            
        if self.br_curr & self.br_mask:
            value = 1
        else:
            value = 0
            
        self.br_mask >>= 1
        return value
    
    def read_len(self):
        len = 1 #default
        # read 0s until 1
        while self.read_bit() == 0:
            len += 1
        return len

    def read_value(self, bits):
        if not bits:
            raise ValueError("bad bits")

        value = 0
        for _ in range(bits):
            value = value << 1
            value |= self.read_bit()
        return value

    def read_u8(self):
        value = self._data[self.offset]
        self.offset += 0x1
        return value

    def read_uv(self):
        data = self._data
        value = 0

        curr = self.read_u8()
        value = (curr & 0x7f)
        if not (curr & 0x80):
            return value

        curr = self.read_u8()
        value = (value << 7) | (curr & 0x7f)
        if not (curr & 0x80):
            return value

        curr = self.read_u8()
        value = (value << 7) | (curr & 0x7f)
        if not (curr & 0x80):
            return value

        curr = self.read_u8()
        value = (value << 7) | (curr & 0x7f)

        return value

    def get_u8(self, pos=0):
        data = self._data
        return data[self.offset + pos]
        
    def get_u16(self, pos=0):
        data = self._data
        val  = data[self.offset + pos + 0] << 8
        val |= data[self.offset + pos + 1] << 0
        return val

    def get_u24(self, pos=0):
        data = self._data
        val  = data[self.offset + pos + 0] << 16
        val |= data[self.offset + pos + 1] << 8
        val |= data[self.offset + pos + 2] << 0
        return val

    def get_u32(self, pos=0):
        data = self._data
        val  = data[self.offset + pos + 0] << 24
        val |= data[self.offset + pos + 1] << 16
        val |= data[self.offset + pos + 2] << 8
        val |= data[self.offset + pos + 3] << 0
        return val

    def get_u64(self, pos=0):
        data = self._data
        val  = data[self.offset + pos + 0] << 56
        val |= data[self.offset + pos + 1] << 48
        val |= data[self.offset + pos + 2] << 40
        val |= data[self.offset + pos + 3] << 32
        val |= data[self.offset + pos + 4] << 24
        val |= data[self.offset + pos + 5] << 16
        val |= data[self.offset + pos + 6] << 8
        val |= data[self.offset + pos + 7] << 0
        return val

#******************************************************************************

class Cli(object):
    def _parse(self):
        description = (
            "Demuxes .moflex videos\n"
        )
        epilog = (
            "examples:\n"
            "  %(prog)s opening.moflex\n"
            "  - demux\n\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument('files', help="Files to get (wildcards work)", nargs='*', default=['*.moflex'])
        p.add_argument('-vi',  '--verbose-info',  help="Some messages (for debugging)", action='store_true')
        p.add_argument('-vd',  '--verbose-debug', help="More messages (for debugging)", action='store_true')
        p.add_argument('-vt',  '--verbose-trace', help="Many messages (for debugging)", action='store_true')
        p.add_argument('-f',  '--full', help="Reads + writes all data from file, not just audio (for debugging)", action='store_true')
        p.add_argument('-r',  '--raw', help="Writes raw-ish audio with custom headers (for debugging)", action='store_true')
        p.add_argument('-i',  '--info', help="Print info only", action='store_true')
        return p.parse_args()

    def start(self):
        args = self._parse()
        if not args.files:
            return

        filenames = []
        for filename in args.files:
            if os.path.isfile(filename): #for files in paths with regex-like format
                filenames += [filename]
            else:
                filenames += glob.glob(filename)

        for filename in filenames:
            if filename.endswith('.audio.moflex'):
                continue
            if filename.endswith('.audioraw.moflex'):
                continue
            if filename.endswith('.full.moflex'):
                continue

            Demoflex(args, filename).start()

if __name__ == "__main__":
    Cli().start()
