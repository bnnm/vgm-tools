# splits XA bigfiles
# (replacement for vgmtoolbox's splitter since its algorithm doesn't work correctly for all files)

import glob, os, struct

XA_MAX_CHANNELS = 32

class XaSplitter:
    def __init__(self, f):
       self.f = f
       self.xa_chans = [None] * XA_MAX_CHANNELS
       self.xa_files = [None] * XA_MAX_CHANNELS
       self.subsongs = 0
       self.name, self.ext = os.path.splitext(f.name)

    def _stop(self):
        for i in range(XA_MAX_CHANNELS):
            if self.xa_files[i]:
                self.xa_files[i].close()
            self.xa_chans[i] = None
            self.xa_files[i] = None

    def _split(self, head, sector):
        curr_info = head

        xa_file     = (curr_info >> 24) & 0xFF
        xa_chan     = (curr_info >> 16) & 0xFF
        xa_submode  = (curr_info >>  8) & 0xFF
       #xa_header   = (curr_info >>  0) & 0xFF

        is_audio = not (xa_submode & 0x08) and (xa_submode & 0x04) and not (xa_submode & 0x02)
        is_eof = (xa_submode & 0x80)

        if xa_chan >= XA_MAX_CHANNELS:
            raise ValueError("XA: too many channels: %x" % (xa_chan))

        if not is_audio:
            return

        # use info without submode to detect new subsongs
        curr_info = curr_info & 0xFFFF00FF;

        # changes for a current channel = new subsong
        if self.xa_chans[xa_chan] != curr_info:
            name = "%s-%04i_%02x%02x%s" % (self.name, self.subsongs, xa_file, xa_chan, self.ext)
            self.subsongs += 1

            self.xa_chans[xa_chan] = curr_info
            self.xa_files[xa_chan] = open(name, 'wb')

        # save current sector's subsong data
        self.xa_files[xa_chan].write(sector)

        # remove info (after handling sector) so next comparison for this channel adds a subsong
        if is_eof:
            if self.xa_files[xa_chan]:
                self.xa_files[xa_chan].close()
            self.xa_chans[xa_chan] = None
            self.xa_files[xa_chan] = None


    def split(self):
        f = self.f
        file = f.name
        sync = f.read(0x0c)

        if sync != b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00':
            return

        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(0)

        if size % 0x930:
            printf("incorrect xa:", file)
            return

        print("splitting", file)

        sectors = size // 0x930
        for i in range(sectors):
            sector = f.read(0x930)
            sync = sector[0x00:0x0c]
            if sync != b'\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x00':
                raise ValueError("incorrect sector", i, sync)

            head_u32, = struct.unpack_from('>I', sector, 0x10)
            self._split(head_u32, sector)

        self._stop()

        print("done")


def main():
    files  = glob.glob('*.xa')
    files += glob.glob('*.str')
    for file in files:
        with open(file, 'rb') as f:
            XaSplitter(f).split()

main()
