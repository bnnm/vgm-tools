# identifies common files and moves them to subdirs
# mostly for weird unity crap with hashed filenames
# 
# ugly I know, to be redone

import os
import sys
import struct


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
    if not os.path.exists(dir):
        os.makedirs(dir)
   
    #print("Renaming " + filename + " to " + dir + "/" + filename)
    os.rename(filename, dir + "/" + filename)

    return

# main
for filename in os.listdir("."):
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


    if (id == 0x40555446): # @UTF
        channels = 0
        type = "criware"

    if (id == 0x4F676753): # OggS
        channels = 0
        type = "ogg"

    if (id == 0x89504E47): # PNG
        channels = 0
        type = "png"
        
        

    if (id == 0x414B4220): # AKB 
        channels = 0
        type = "akb"

    if (id == 0x41465332): # AFS2
        channels = 0
        type = "awb"

    if (id == 0x41465300): # AFS 
        channels = 0
        type = "afs"

    if (id == 0x41465300): # AFS 
        channels = 0
        type = "afs"

    if ((id & 0xFFFF0000) == 0x80000000):
        channels = 0
        type = "adx"

    if (id == 0x556E6974): # Unit
        channels = 0
        type = "unity"

    if (id == 0x504B0304): # zip
        channels = 0
        type = "zip"

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

    if (id == 0x424B4844): # BKHD
        #channels = header.get_u16le(0x16)
        channels = 0
        type = "bkhd"

    if (id == 0x73616266): # sabf
        channels = 0
        type = "sab"

    if type == "":
        print("unknown file %s" % filename)
        continue

    if channels <= 0:
        dir = "%s" % (type)
    else:
        dir = "%s_%ich" % (type, channels)
    move_file(filename, dir)

#wait = input("done")
