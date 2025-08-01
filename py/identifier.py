# identifies common files and moves them to subdirs
# mostly for weird unity crap with hashed filenames
# 
# ugly I know, to be redone

import os
import sys
import struct
import glob

fourcc_type = {
    b'@UTF': 'acb-acf',
    b'OggS': 'ogg',
    b'AFS2': 'awb',
    b'AKB ': 'akb',
    b'AFS\0': 'afs',
    b'BKHD': 'bnk',
    b'AKPK': 'apk',
    b'sabf': 'sab',
    b'Unit': 'unity',
    b'MThd': 'midi',
    b'CPK ': 'cpk',
    b'CRID': 'usm',
    b'srcd': 'srcd', #reengine
    b'KTSR': None, #manual
    b'KTSC': 'ktsc',
    b'RIFF': 'riff', #wav or otherwise
    b'RIFX': 'rifx', #wav or otherwise
    b'XWAV': 'xwv',
    b'caff': 'caf',
    b'\x89PNG': 'png',
    b'ID3\x03': 'mp3',
    b'ID3\x04': 'mp3',
    b'PK\x03\x04': 'zip',
}
fourcc2_type = {
    b'ftyp': 'mp4',
}

class Reader(object):
    def __init__(self, buf):
       #self.file = file
       self.buf = buf
       self.be = False

    #def get_u32le_f(self, offset):
    #   self.file.seek(offset)
    #   return struct.unpack('<I', self.file.read(4))[0]

    def get_u32le(self, offset):
       return struct.unpack('<I', self.buf[offset:offset+4])[0]

    def get_u32be(self, offset):
       return struct.unpack('>I', self.buf[offset:offset+4])[0]

    def get_u16le(self, offset):
       return struct.unpack('<H', self.buf[offset:offset+2])[0]

    def get_u16be(self, offset):
       return struct.unpack('>H', self.buf[offset:offset+2])[0]

    def get_u8(self, offset):
       return struct.unpack('B', self.buf[offset:offset+1])[0]

    def get_u32(self, offset):
       if self.be:
           return self.get_u32be(offset)
       else:
           return self.get_u32le(offset)

    def get_u16(self, offset):
       if self.be:
           return self.get_u16be(offset)
       else:
           return self.get_u16le(offset)

    def set_endian(self, big_endian):
        self.be = big_endian

def move_file(filename, dir):
    outpath = dir + "/" + filename
    outdir = os.path.dirname(outpath)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
   
    #print("Renaming " + filename + " to " + outpath)
    os.rename(filename, outpath)

    return


def main():
    #files = glob.glob('**/*', recursive=True)
    files = glob.glob('*', recursive=True)
    for filename in files: #os.listdir("."):
        if not os.path.isfile(filename):
            continue

        #print("file %s" % filename)
        in_file = open(filename, "rb")
        data = in_file.read(0x60)
        in_file.close()
        
        if (len(data) < 0x10):
            continue

        header = Reader(data)

        type = ""
        channels = None
        srate = None
        id = header.get_u32be(0x00)
        id2 = header.get_u32be(0x04)
        fourcc = data[0:4]
        fourcc2 = data[4:8]

        type = fourcc_type.get(fourcc)
        if not type:
            type = fourcc2_type.get(fourcc2)

        if ((id & 0xFFFF0000) == 0x80000000):
            type = "adx"
            channels = header.get_u8(0x07)
            srate = header.get_u32be(0x08)

        if ((id & 0x7f7f7f7f) == 0x48434100): # HCA
            channels = header.get_u16le(0x0c)
            type = "hca"

        if fourcc == b'KTSR':
            if   id2 == 0x777B481A:
                type = "ktsl2asbin"
            elif id2 == 0x0294DDFC:
                type = "ktsl2stbin"
            elif id2 == 0xC638E69E:
                type = "ktsl2gcbin"

        if not type:
            #print("unknown file %s" % filename)
            continue

        subdir = ''
        if fourcc == b'XWAV':
            streams = header.get_u8(0x27)
            if streams > 1:
                channels = 6
            else:
                channels = header.get_u8(0x47)

        if fourcc == b'RIFX':
            channels = header.get_u16be(0x16)
        if fourcc == b'RIFF':
            channels = header.get_u16le(0x16)

        if fourcc == b'AKB ':
            channels = header.get_u8(0x0d)
            subdir = '%s-' % (header.get_u16le(0x0e))

        if channels:
            subdir = subdir + '%ich' % (channels)
        if srate:
            subdir = subdir + '-%i' % (srate)

        if subdir:
            dir = "%s/%s" % (type, subdir)
        else:
            dir = "%s" % (type)

        move_file(filename, dir)

main()
