# phantom breaker / ogre tale / etc file decryptor

from __future__ import division
import os
import sys
import glob
import argparse
import struct
import re

# by bnnm, info: https://forum.xentax.com/viewtopic.php?t=6752
#
# howto:
# - extract game files with pb_extract.py (not all are encrypted)
# - decrypt extracted files with pb_decrypt.py, needs byte key
#   tries to guess key, but preferably set target header value, like
#   "-t 52" for RIFF (R=0x52) sounds, or "-t 4D" for MSCF (M=0x4D) bgm
# - real file names are sometimes in the exe as a table (real name to 'hashed' name)

def parse():
    description = (
        "decrypts Phantom Breaker files, with key or guessing if possible"
    )
    epilog = (
        "examples:\n"
        "  %(prog)s *\n"
    )

    parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("files", help="files to get (wildcards work)")
    parser.add_argument("-k","--keyval", help="decryption byte")
    parser.add_argument("-t","--target", help="target byte expected to appear at file start")
    parser.add_argument("-g","--guesssize", type=int, default=0x4000, help="max bytes to use to guess size, if key isn't given")
    
    return parser.parse_args()

class BufferReader(object):
    def __init__(self, buf, big_endian):
       #self.file = file
       self.buf = buf
       self.be = big_endian

    #def get_u32le_f(self, offset):
    #   self.file.seek(offset)
    #   return struct.unpack('<I', self.file.read(4))[0]

    def get_u8(self, offset):
       return self.buf[offset]

    def get_u16le(self, offset):
       return struct.unpack('<H', self.buf[offset:offset+2])[0]

    def get_u16be(self, offset):
       return struct.unpack('>H', self.buf[offset:offset+2])[0]

    def get_u16(self, offset):
       if self.be:
           return self.get_u16be(offset)
       else:
           return self.get_u16le(offset)

    def get_u32le(self, offset):
       return struct.unpack('<I', self.buf[offset:offset+4])[0]

    def get_u32be(self, offset):
       return struct.unpack('>I', self.buf[offset:offset+4])[0]

    def get_u32(self, offset):
       if self.be:
           return self.get_u32be(offset)
       else:
           return self.get_u32le(offset)

def is_file_ok(args, glob_file):
    if not os.path.isfile(glob_file):
        return False

    if glob_file.endswith(".py"):
        return False
    return True
    
    
def decrypt(data, key, pos):
    data_len = len(data)
    key_len = len(key)
    for i in range(0,data_len):
        data[i] ^= key[(pos+i) % key_len]
    return data

def main(): 
    args = parse()

    # get target files
    glob_files = glob.glob(args.files)
    
    chunk_size = 0x4000
    # process matches and add to output list
    files = []
    for glob_file in glob_files:
        if not is_file_ok(args, glob_file):
            continue
        print("decrypting " + glob_file + "...")


        # per-file encryption seems to depend on file number and something else not known
        # instead allow some basic decryption methods
        if args.keyval:
            # exact byte given
            keyval = bytearray.fromhex(args.keyval)[0]
            #keyval = bytes.fromhex(args.keyval)  #python3
        elif args.target:
            # expected first byte in file (like 52 for RIFF or 4D for MSCF)
            keytarget = bytearray.fromhex(args.target)[0]
            with open(glob_file, 'rb') as infile:
                data = bytearray(infile.read(0x04))
                keyval = data[0] ^ keytarget
            #key = bytes.fromhex(args.target)  #python3
            #print("target key: " + hex(keyval))

        else:
            # guessing, if file has enough blank parts it's pretty possible
            counts = [0]*0x100 #init list, what
            with open(glob_file, 'rb') as infile:
                data = bytearray(infile.read(args.guesssize))
                # base key appears in many places, find candidate
                for i in range (0,len(data)):
                    n = i % 0x100
                    sub = 0 ^ (((n//2)%4)<<1) ^ (((n//32)%8)<<5)
                    counts[data[i] ^ sub] += 1
                pos = 0
                max = 0
                for i in range (0,len(counts)):
                    if counts[i] > max:
                        pos = i
                        max = counts[i]
            keyval = pos
            #print("guessed key: " + hex(keyval))

        #make final key
        key = bytearray(0x100)
        for i in range (0,0x100):
            key[i] = keyval ^ (((i//2)%4)<<1) ^ (((i//32)%8)<<5)

        #decrypt
        size = os.path.getsize(glob_file)
        with open(glob_file, 'rb') as infile:
            filename_out = glob_file
            if filename_out.endswith('.enc'):
                filename_out = filename_out[:-4]

            # guess extension
            buf = bytearray(infile.read(0x04))
            buf = decrypt(buf, key, 0)
            br = BufferReader(buf,False)
            infile.seek(0)
            id = br.get_u32be(0x00)
            if id == 0x52494646: #RIFF
                filename_out += ".lwav"
            elif id == 0x4D534643: #MSFC
                filename_out += ".msf"
            else:
                filename_out += ".dec"

            with open(filename_out, 'wb') as outfile:
                for i in range(0, size, chunk_size):
                    data = bytearray(infile.read(chunk_size))
                    data_dec = decrypt(data, key, i)
                    outfile.write(data_dec)

if __name__ == "__main__":
    main()
 
