# Dumps files from Lego Island .SI files.
# https://www.legoisland.org/wiki/Interleaf_File
#
# Note this only dumps the raw contents and doesn't convert anything.
# This means .wav files aren't playable as-is (use vgmstream + txth)

import argparse, os, struct, glob
from collections import defaultdict

# blah\blah.blah -> blah~blah.blah
# mainly for convenience with .txth
FLATTEN_PATHS = True

def remove_basepath(path):
    path = path.replace("\\", "/")

    while path.startswith("/"):
        path = path[1:]

    if len(path) >= 2 and path[1] == ":":
        path = path[2:]
        while path.startswith("/"):
            path = path[1:]

    return path.replace("/", "\\")

def path_mkdirs(path):
    dir = os.path.dirname(path)

    if dir:
        os.makedirs(dir, exist_ok=True)


def align2(size):
    return (size + 1) & ~1

def read_u16(data, offset):
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def read_s32(data, offset):
    return struct.unpack_from("<i", data, offset)[0]

def read_fcc(data, offset):
    return data[offset : offset + 0x04]

def read_strz(data, offset):
    end = data.find(b"\x00", offset)
    if end == -1:
        raise ValueError("not null terminator")

    return data[offset:end].decode("utf-8", errors="replace")


class Chunk:
    def __init__(self, offset, data):
        self._parse(offset, data)

    def _parse(self, offset, data):
        self.offset = offset #absolute
        self.fourcc = read_fcc(data, 0x00)
        self.size = read_u32(data, 0x04)
        self.data = None

        data_offset = 0x08
        data_end = data_offset + self.size
        if data_end > len(data):
            raise ValueError(f"incorrect chunk found: f={self.fourcc} o={self.offset:08x} size={self.size + 0x08:08x} ")

        self.data = data[data_offset : data_end]

    def __repr__(self):
        return (
            f"Chunk(name={self.fourcc}, "
            f"offset={self.offset:08x}, "
            f"size={self.size + 0x08:x})"
        )

class MxObInfo:
    def __init__(self):
        self.type = None
        self.name = None
        self.id = None
        self.path = None
        self.fcc = None


class Unpacker:
    def __init__(self, filename, args):
        self.filename = filename
        self.mxst_count = 0
        self.mxob_info = {} #ID > info
        self.paths_written = set()
        self.test = args.test
        self.debug = args.debug

    def log_chunk(self, info, chunk=None):
        if self.debug:
            #print(" " * self.depth, info, chunk)
            if chunk:
                print(info, chunk)
            else:
                print(info)

    def iter_chunks(self, data, base_offset):
        offset = 0
        end = len(data)

        while offset < end:
            chunk_offset = base_offset + offset
            chunk_data = data[offset : ]
            
            test_fourcc = read_fcc(chunk_data, 0x00)

            # ugly patches for buggy files
            # usually some odd value after a MxCh and next MxCh (aligned to 0x10?

            # ACT2MAIN.SI
            if test_fourcc == b'\xAC\xEA\x99\xFC':
                offset += 0x04
                continue

            # INFOMAIN.SI
            if test_fourcc == b'\x27\x09\x9A\xFF':
                offset += 0x06
                continue

            # ISLE.SI
            if test_fourcc in (b'\xAD\xF0\x4D\x78', b'\x60\x03\x4D\x78', b'\xAC\xF4\x4D\x78'):
                offset += 0x02
                continue
            if test_fourcc == b'\x5A\xFE\x4A\xFE':
                offset += 0x06
                continue

            chunk = Chunk(chunk_offset, chunk_data)
            yield chunk

            offset += 0x08 + align2(chunk.size)


    def parse_mxob_list(self, data, base_offset):
        list_chunk = Chunk(base_offset, data)

        if list_chunk.fourcc != b'LIST':
            raise ValueError("unknown MxOb LIST")

        offset = 0x00
        mxch    = read_fcc(list_chunk.data, offset)
        if mxch != b'MxCh':
            raise ValueError("unknown MxOb MxCh")
        offset += 0x04

        # number of MxOb, size, or RANDOM (seen in COPTER.SI)
        test_fourcc = read_fcc(list_chunk.data, offset)
        if test_fourcc == b'RAND':
            rand_desc   = read_strz(list_chunk.data, offset) #typically empty
            offset += len(rand_desc) + 0x01
            rand_count  = read_u32(list_chunk.data, offset)
            offset += 0x04 + rand_count * 0x02
        else:
            offset += 0x04

        list_data = list_chunk.data[offset : ]
        list_offset = list_chunk.offset + 0x08 + offset

        for chunk in self.iter_chunks(list_data, list_offset):
            self.log_chunk('parse_mxob_list', chunk)

            if chunk.fourcc != b"MxOb":
                raise ValueError("unknown MxOb")

            self.parse_mxob(chunk.data, chunk.offset)
        

    def parse_mxob(self, data, base_offset):
        obj = MxObInfo()

        offset = 0x00
        # 03=SMK, 04=WAV, 07=container, 0a=STL (bmp), etc
        obj.type        = read_u16(data, offset)
        offset += 0x02

        obj.desc        = read_strz(data, offset) #typically empty
        offset += len(obj.desc) + 0x01
        
        obj.unk         = read_u32(data, offset) #alwayx 0?
        offset += 0x04

        obj.name        = read_strz(data, offset)
        offset += len(obj.name) + 0x01

        obj.id          = read_u32(data, offset)
        offset += 0x04
        offset += 0x58 #a bunch of unknown data

        obj.extra_size  = read_u16(data, offset) #rarely used description (JUKEBOXW)
        offset += 0x02
        offset += obj.extra_size

        obj_list        = read_fcc(data, offset)
        if obj_list == b'LIST':
            self.log_chunk('MxOb: LIST header')
            list_data = data[offset : ]
            list_offset = base_offset + offset

            self.parse_mxob_list(list_data, list_offset)
        else:
            self.log_chunk('MxOb: simple header')
            obj.path    = read_strz(data, offset)
            offset += len(obj.path) + 0x01
            offset += 0x0c #stuff?

            obj.fcc     = read_fcc(data, offset)
            offset += 0x04

            prev = self.mxob_info.get(obj.id)
            if prev:
                raise ValueError("repeated MxOb ID found")
            self.mxob_info[obj.id] = obj

        return {}


    def parse_mxda(self, data, base_offset):
        payloads = defaultdict(bytearray)

        for chunk in self.iter_chunks(data, base_offset):
            self.log_chunk("parse_mxda", chunk)
            
            if chunk.fourcc == b"pad ":
                continue

            if chunk.fourcc != b"MxCh":
                continue

            chunk_size = len(chunk.data)
            if chunk_size < 0x0e:
                continue

            flags        = read_u16(chunk.data, 0x00)
            object_id    = read_u32(chunk.data, 0x02)
            milliseconds = read_s32(chunk.data, 0x06)
            payload_size = read_u32(chunk.data, 0x0a)

            # chunks may have "split data" flag 0x10: first chunk payload_size 
            # is the full size including following chunks that use 0x10
            # To simplify just use main chunk size
            if flags == 0x10:
                payload_size = chunk_size - 0x0e

            payload_offset = 0x0e
            payload_end = payload_offset + payload_size
            payload_max = len(chunk.data)

            #if payload_end > chunk_size:
            #    raise ValueError(f"wrong payload found: payload={payload_end:08x} vs size={chunk_size:08x}")

            payload = chunk.data[payload_offset : payload_end]

            payload_data = payloads[object_id]
            payload_data.extend(payload)

        return payloads

    def write_mxst(self, object_id, payload):
        if len(payload) == 0:
            return
        
        obj = self.mxob_info.get(object_id)
        if not obj:
            raise ValueError(f"couldn't find MxOb for ID {object_id:04d}")

        filename = f"{self.basename}_{self.mxst_count:02d}_{object_id:04d}.bin"
        
        path = remove_basepath(obj.path)
        if FLATTEN_PATHS:
            path = path.replace('\\', '~')
            path = path.replace('/', '~')

        filename = f"{self.basename}/{path}"
        path_mkdirs(filename)

        if not self.test:
            with open(filename, "wb") as f:
                f.write(payload)

        print(f"wrote {filename}")
        

    def parse_mxst(self, data, base_offset):

        for chunk in self.iter_chunks(data, base_offset):
            self.log_chunk("parse_mxst", chunk)

            if chunk.fourcc == b"pad ":
                continue

            if chunk.fourcc == b"MxOb":
                self.parse_mxob(chunk.data, chunk.offset + 0x08)
                continue

            if chunk.fourcc != b"LIST":
                continue

            if len(chunk.data) < 0x04:
                continue

            list_type = read_fcc(chunk.data, 0x00)
            if list_type != b"MxDa":
                raise ValueError("expected MxDa")

            list_data = chunk.data[0x04 : ]
            list_offset = chunk.offset + 0x08 + 0x04

            payloads = self.parse_mxda(list_data, list_offset)

            for object_id, payload in payloads.items():
                self.write_mxst(object_id, payload)

            self.mxst_count += 1


    def parse_mxst_list(self, data, base_offset):

        for chunk in self.iter_chunks(data, base_offset):
            self.log_chunk("parse_mxst_list", chunk)
            
            if chunk.fourcc == b'pad ':
                continue

            if chunk.fourcc != b"MxSt":
                raise ValueError(f"unexpected chunk {chunk.fourcc}")

            mxst_data = chunk.data
            mxst_offset = chunk.offset + 0x08

            self.parse_mxst(mxst_data, mxst_offset)


    def parse_riff(self, data):

        if len(data) < 0x0c:
            raise RuntimeError("File too small")

        riff_fourcc = read_fcc(data, 0x00)

        if riff_fourcc != b"RIFF":
            raise RuntimeError("Not a RIFF file")

        riff_size = read_u32(data, 0x04)
        riff_type = read_fcc(data, 0x08)

        if riff_type != b"OMNI":
            print(f"Warning: RIFF type is {riff_type!r}")

        riff_end = min(len(data), 0x08 + riff_size)
        riff_data = data[0x0c : riff_end]
        riff_offset = 0x0c

        for chunk in self.iter_chunks(riff_data, riff_offset):
            self.log_chunk("parse_riff", chunk)

            if chunk.fourcc == b"pad ":
                continue

            if chunk.fourcc != b"LIST":
                continue

            if len(chunk.data) < 0x04:
                continue

            list_type = read_fcc(chunk.data, 0x00)
            if list_type != b"MxSt":
                continue

            list_data = chunk.data[0x04 : ]
            list_offset = chunk.offset + 0x08 + 0x04

            self.parse_mxst_list(list_data, list_offset)

    def process_obj_info(self):
        lines = []
        for obj_id in self.mxob_info:
            obj = self.mxob_info[obj_id]
            lines.append(f'{obj.name} : {obj.path}')

        filename = f'{self.basename}_info.txt'
        with open(filename, "w") as f:
             f.write('\n'.join(lines))


    def parse_file(self):
        filename = self.filename
        with open(filename, "rb") as f:
            data = f.read()
        self.basename = os.path.splitext(os.path.basename(filename))[0]

        self.parse_riff(data)
        self.process_obj_info()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", default=['*.SI'])
    parser.add_argument("-t", '--test', help="don't write files", action='store_true')
    parser.add_argument("-d", '--debug', help="extra debug info", action='store_true')
    args = parser.parse_args()


    files = []

    for pattern in args.files:
        # meh...
        if "*" in pattern or "?" in pattern:
            files = glob.glob(pattern)
            files.extend(files)
        else:
            files.append(pattern)

    for filename in files:
        Unpacker(filename, args).parse_file()


if __name__ == "__main__":
    main()
