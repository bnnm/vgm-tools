#!/usr/bin/env python3
from __future__ import division
import os, sys, glob, argparse, struct, re

# by bnnm, info: https://forum.xentax.com/viewtopic.php?t=6752
# v1 - original
# v2 - fix python3
# v3 - improve drag and drop, names.txt
#
# howto:
# - extract game files with pb_extract.py (not all are encrypted)
# - decrypt extracted files with pb_decrypt.py, needs byte key
#   tries to guess key, but preferably set target header value, like
#   "-t 52" for RIFF (R=0x52) sounds, or "-t 4D" for MSCF (M=0x4D) bgm
# * names can be found in .exe: there are 2 tables somewhere inside, 
#   with all original names ("FP_BGM") then all mangled names ("01485305"). 

#todo fix extract in some cases (bad offsets)

test_size = 0x8000

def parse():
    description = (
        "extracts Phantom Breaker files"
    )
    epilog = (
        "examples:\n"
        "  %(prog)s *\n"
    )

    parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("files", help="files to get (wildcards work)")
    
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

    names = {}
    try:
        with open('names.txt') as f:
            for line in f:
                line = line.replace('"' , '')
                mangled, name = line.split("=")
                name = name.strip()
                mangled = mangled.strip()
                mangled, _ = os.path.splitext(mangled)
                names[mangled] = name
    except:
        pass

    # get target files
    glob_files = glob.glob(args.files)

    #fill header key
    prevkey = 0x79
    key = bytearray(0x80)
    for i in range(0,0x80):
        key[i] = prevkey
        prevkey += 0x6
        if prevkey > 0xFF:
            prevkey -= 0x100
    
    chunk_size = 0x8000
    # process matches and add to output list
    files = []
    for glob_file in glob_files:
        if not is_file_ok(args, glob_file):
            continue

        base_name = os.path.basename(glob_file)
        base_name, _ = os.path.splitext(base_name)
        if base_name in names:
            out_name = names[base_name]
            print("extracting %s (%s)..." % (glob_file, out_name))
        else:
            out_name = base_name
            print("extracting %s..." % (glob_file))

        with open(glob_file, 'rb') as infile:
            buf = infile.read(0x04)
            br = BufferReader(buf,False)
            infile.seek(0)
            
            if br.get_u16(0x02) != 0xFFFF:
                print("not encrypted")
                continue
                
            # header is encrypted
            data = bytearray(infile.read(test_size))
            data = decrypt(data, key, 0)
            br = BufferReader(data,False)

            # 0x00-0x08: no idea, maybe config decrypted other way, probably
            # something somewhere is setting sizes but we do it in a dumber way
            
            # a file header has N offsets to tables, then tables, each with M files
            # no idea why there are multiples and not just one big table

            # find table offsets
            table_offsets = []
            offset = 0x08
            while(1):
                table_offset = br.get_u32(offset)
                #print("table found " + hex(table_offset))

                if table_offset == 0xFFFFFFFF: #ignore
                    offset += 0x04
                    continue  
                if table_offset > 0x10000:
                    table_start = offset
                    break
                offset += 0x04
                table_offsets.append(table_offset)
            tables_offset = offset

            #guess header size
            header_size = tables_offset
            # read last table
            br.get_u32(tables_offset - 0x04) 

            offset = 0
            # read tables and put file offsets
            tables = []
            for table_offset in table_offsets:
                offset = tables_offset + table_offset
                #print("table at " + hex(offset))

                # base count
                file_count = br.get_u16(offset)
                offset += 0x02

                #some kind of lacing values?
                skip = file_count // 8
                if file_count % 8 > 0:
                    skip += 1
                offset += skip
                #print("files=" + str(file_count) + ", skip: " + str(skip))

                #actual files
                files = []
                for i in range(0,file_count):
                    file_offset = br.get_u32(offset+0x00)
                    file_size = br.get_u32(offset+0x04)
                    #print("table 0x%04x = 0x%08x, 0x%x" % (offset, file_offset, file_size))
                    offset += 0x08

                    if file_offset == 0xFFFFFFFF or file_size == 0xFFFFFFFF:
                        continue
                    if file_size == 0:
                        continue
                    files.append( (i, file_offset, file_size) )
                tables.append(files)
            end_offset = offset

            # skip padding
            while(1):
                val = br.get_u8(end_offset)
                if val != 0x00:
                    break
                end_offset += 0x01
                    
            if True:
                with open(glob_file + ".header", 'wb') as outfile:
                    outfile.write(data[0:end_offset])

            # write files read from tables
            count = 0
            for table in tables:
                for files in table:
                    file_number = files[0]
                    file_offset = files[1] + end_offset
                    file_size = files[2]
                    #print("off=" + hex(files[1]) + " + " + hex(end_offset)+ ", s=" + hex(file_size))

                    file_name = out_name + "/" + out_name + "__" + str(count).zfill(3) + ".enc"
                    os.makedirs(out_name, exist_ok=True)
                    count += 1

                    with open(file_name, 'wb') as outfile:
                        total = 0
                        infile.seek(file_offset)
                        while total < file_size:
                            read = chunk_size
                            if total + read > file_size:
                                read = file_size - total
                            buf = infile.read(read)
                            outfile.write(buf)
                            total += len(buf)
                            if len(buf) == 0:
                                print("error: bad file size " + str(file_size) + " at " + str(file_offset))
                                exit()
if __name__ == "__main__":
    main()
 
