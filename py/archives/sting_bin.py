# extracts obfuscated data from Sting's newer games/ports (data.bin) by bnnnm
# * obfuscation reversed from various exes/android libs (w/ symbols)

import os, zlib, struct
import codecs
import hashlib

FILTERS = ['/sound/', '/movie/'] #text inside path (case insensitive)
LIST_ONLY = False
UNZIP_FILES = True
WRITE_HEADER = False

class StingExtractor:
    def _extract_file(self, offset, size, path, filename, is_zip):
        f = self._f
        offset += self.data_offset

        upath = path.decode('utf-8')
        ufilename = filename.decode('utf-8')
        uout = upath + ufilename

        if FILTERS and not any(filter.lower() in uout.lower() for filter in FILTERS):
            print(uout, "(skipped)")
            return

        print(uout) #, "(offset=%08x, size=%08x)" % (offset, size))
        if LIST_ONLY:
            return

        f.seek(offset)
        buf = f.read(size)
        buf = bytearray(buf)
        self._deobfuscate(buf, ufilename)
        
        if UNZIP_FILES and is_zip: #buf[0x04] == 0x78:
            try:
                buf = self._unzip(buf)
            except:
                pass

        try:
            os.makedirs(upath)
        except:
            pass
            
        with open(uout, 'wb') as f:
            f.write(buf)


    def _get_name(self, buf, offset):
        offset += self.names_offset
        end = buf.index(b'\x00', offset)
        return buf[offset:end]

    def _parse_entry(self, buf, offset, name):
        name_offset, entry_flags, entry_offset = struct.unpack_from('<III', buf, offset)

        is_dir = entry_flags & 0x80000000
        is_zip = entry_flags & 0x40000000
        entry_length = entry_flags & 0x0FFFFFFF

        basename = self._get_name(buf, name_offset)
        
        #print(name, "name=%x, flags=%x, offset=%x" % (name_offset, entry_flags, entry_offset))
        if is_dir:
            entry_offset += self.entries_offset
            name = name + basename + b'/'
            for i in range(entry_length):
                self._parse_entry(buf, entry_offset, name)
                entry_offset += 0x0c
        else:
            self._extract_file(entry_offset, entry_length, name, basename, is_zip)


    # saved like
    # dir (N files)
    #   dir (N files)
    #   ...
    #     dir (N files)
    #     ...
    #   file
    #   ...
    #     file
    #     ...
    #       file
    #       ...
    def _parse_header(self, buf):
        entries_size, names_size = struct.unpack_from('<II', buf, 0x00)
        entries = entries_size // 0x0c

        self.entries_offset = 0x08
        self.names_offset = 0x08 + entries_size

        self._parse_entry(buf, self.entries_offset, b'./')

    def _unzip(self, buf):
        # not neede by zlib but maybe should clamp?
        unzip_size, = struct.unpack_from('<I', buf, 0x00)

        # standard zlib windowsize 15
        dec = zlib.decompressobj(15)
        buf = dec.decompress(buf[4:])
        return buf

    # sge::Resource::Resource
    # sge::Resource::defaultObfusDecoder
    def _deobfuscate(self, buf, key):
        key = codecs.encode(key, 'rot13')
        key = key.encode('utf-8')

        md5key = hashlib.md5(key).digest()

        for i in range(len(buf)):
            buf[i] ^= md5key[i % 0x10]

    def read_header(self):
        f = self._f

        buf = f.read(0x08)
        head_size, data_size = struct.unpack('<II', buf)

        self.data_offset = 0x08 + head_size

        buf = f.read(head_size)
        buf = bytearray(buf)

        self._deobfuscate(buf, 'InfoData') #header key

        out = self._unzip(buf)
        return out

    def _parse(self, filename):
        if not os.path.exists(filename):
            return

        print("opening file " + filename)
        with open(filename, 'rb') as f:
            self._f = f

            buf = self.read_header()
            self._parse_header(buf)

        if WRITE_HEADER:
            with open(filename + '.hdr', 'wb') as f:
                f.write(buf)

    def extract(self, filename):
        self._parse(filename)


StingExtractor().extract('data.bin')
StingExtractor().extract('data2.bin')
StingExtractor().extract('data_sound.bin')
