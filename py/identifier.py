# identifies common files and moves them to subdirs
# mostly for weird unity crap with hashed filenames
# 
# ugly I know, to be redone

import os
import sys
import struct
import glob


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
    files = glob.glob('**/*', recursive=True)
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
        channels = 0
        id = header.get_u32be(0x00)
        fourcc = data[0:4]
        fourcc2 = data[4:8]
        
        fourcc_type = {
            b'@UTF': 'acb-acf',
            b'OggS': 'ogg',
            b'AFS2': 'awb',
            b'AKB ': 'akb',
            b'AFS\0': 'adx',
            b'BKHD': 'bkhd',
            b'sabf': 'sab',
            b'Unit': 'unity',
            b'MThd': 'midi',
            b'CPK ': 'cpk',
        }
        fourcc2_type = {
            b'ftyp': 'mp4',
        }

        type = fourcc_type.get(fourcc)
        if not type:
            type = fourcc2_type.get(fourcc2)

        if (id == 0x89504E47 or id == 0x89706E67): # PNG
            channels = 0
            type = "png"

        if ((id & 0xFFFF0000) == 0x80000000):
            channels = 0
            type = "adx"

        if (id == 0x504B0304): # zip
            channels = 0
            type = "zip"

        if (id == 0x49443303 or id == 0x7FFB9044 or id == 0x7FFB9064): 
            channels = 0
            type = "mp3"

        if (id == 0x58574156): # xwav
            streams = header.get_u8(0x27)
            if streams > 1:
                channels = 6
            else:
                channels = header.get_u8(0x47)
            type = "xwv"

        if ((id & 0x7f7f7f7f) == 0x48434100): # HCA
            channels = header.get_u16le(0x0c)
            type = "hca"

        if (id == 0x52494658): # RIFX
            channels = header.get_u16le(0x16)
            type = "riff"

        if (id == 0x52494646): # RIFF
            channels = header.get_u16le(0x16)
            type = "riff"

        if not type:
            #print("unknown file %s" % filename)
            continue

        if channels <= 0:
            dir = "%s" % (type)
        else:
            dir = "%s_%ich" % (type, channels)
        move_file(filename, dir)

main()
