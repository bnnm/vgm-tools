# demuxes Konami blocks found in KCEJ games (often in .sdt and .dat)
#
# v1 by Nisto
# v2 by bnnm:
# - endianness detection for MGS4
# - dump .adpcm data directly (use .txth instead):
#       0x00(4): data size
#       0x04(2): always 0x7f? (volume?)
#       0x06(2): sample rate
#       0x08(1): channels
#       0x09(1): flag? (rare)
#       0x0a(1): codec (0x00=PSX, 0x01=custom pcm8, 0x02=adpcm?, 0x11=MSADPCM)
#       0x0b(1): null?
#       0x0c(4): null?
#       interleave 0x800?
# - dump all files in .dat (these should have a TOC somewhere though)
# - filter by id
# - other tweaks

# todo read header ID on close to get extension (some block_types are shared)
#      (must be on close as registered files don't always start immediatedly)

import os
import sys
import struct


# maps ids that contain padding blocks (must be skipped to get correct data)
padding_type_map = {
    0x00010001,     #needed
    0x00020001,     #needed
    0x00030001,     #probably unneeded
    0x00040001,     #probably unneeded
    0x00050001,     #probably unneeded
    0x00110001,     #needed
}

# maps ids to extensions (not all are correct)
extension_map = {
    # "sdx" audio
    0x00000001: "vgmstream",# ZOE/MGS2 audio
    0x00010001: "mta2",     # MGS4 BGM
    0x00020001: "mta2",     # MGS4 voices
    0x00030001: "msf",      # MGS3 HD (PS3)
	0x00040001: "xwma",     # MGS3 HD (X360)
	0x00050001: "9tav",     # MGS3 HD (Vita)
    0x00100001: "vag",      # MGS3 VAG1/VAG2 (PS2/PS3)
    0x00110001: "mtaf",     # MGS3 (PS2/PS3)

    0x00000002: "dmx",      # MGS4, MGS3 HD, ZOE HD
    0x00010002: "dmx_1",    # MGS3 HD
    0x00020002: "dmx_2",    # MGS3 HD
    0x00030002: "dmx_3",    # MGS3 HD
    0x00040002: "dmx_4",    # MGS3 HD

	0x00000003: "nrm",

    0x00000004: "sub",      # MGS4, MGS3 HD (with "PACB")
	0x00010004: "sub_en",   # HD remasters (type not on MGS2/3 PS2 executable)
	0x00020004: "sub_fr",   # "
	0x00030004: "sub_de",   # "
	0x00040004: "sub_it",   # "
	0x00050004: "sub_es",   # "
	0x00060004: "sub_jp",   # "
	0x00070004: "sub_jp",   # "

    0x00000005: "dmx5",     # HD remasters only

    0x00000006: "_bpx",     # MGS2 HD
    0x00010006: "_bpx",     # 
    0x00020006: "_bpx",     # 
    0x00030006: "_bpx",     # 
    0x00040006: "_bpx",     # 
    0x00050006: "_bpx",     # 
    0x00060006: "_bpx",     # 
    0x00070006: "_bpx",     # 

    0x00000007: "_vid",     # vid? (from demux_dat)

    0x0000000c: "pac",      # MGS2 XBOX (MPEG2 video)
    
    0x0000000d: "pac",      # MGS2 XBOX (MPEG2 video)
    
	0x0000000e: "pss",      # MGS2 PS2 (MPEG2 video)
	0x0002000e: "_mov4",    # MGS4 PS3 (unknown video)
    
	0x0000000f: "ipu",      # MGS2 PS2 (MPEG2 video)

    0x00000020: "m2v",      # HD remasters (all consoles, regardless of format)
    
#   0x00000010: "start",    # "file start" control block (not data)
#   0x000000f0: "end",      # "file end" control block (not data)
}

#header_id_map = {
#    "MTAF": "mtaf",
#    "MTA2": "mta2",
#    "OggS": "ogg",
#    "9TAV": "9tav",
#    "VAG1": "vag",
#    "VAG2": "vag",
#}

class Reader(object):
    def __init__(self, buf, big_endian):
       #self.file = file
       self.buf = buf
       self.be = big_endian

    #def get_u32le_f(self, offset):
    #   self.file.seek(offset)
    #   return struct.unpack('<I', self.file.read(4))[0]

    def get_u32le(self, offset):
       return struct.unpack('<I', self.buf[offset:offset+4])[0]

    def get_u32be(self, offset):
       return struct.unpack('>I', self.buf[offset:offset+4])[0]

    def get_u32(self, offset):
       if self.be:
           return self.get_u32be(offset)
       else:
           return self.get_u32le(offset)

def get_extension(block_id):
    if block_id in extension_map:
        extension = ".%s" % (extension_map[block_id])
    else:
        extension = ".%08x.bin" % (block_id)

    return extension

    
           
def extract_sdt(sdt_path, filter_type, filter_subtype):
    total_files = 0
    is_dat = sdt_path.lower().endswith(".dat")

    sdt = open(sdt_path, "rb")
    sdt_size = os.path.getsize(sdt_path)
    basename = os.path.splitext(os.path.basename(sdt_path))[0]
    basedir = os.path.dirname(sdt_path)

    # detect endianness
    buf = sdt.read(0x10)
    block_size_be = Reader(buf, True).get_u32(0x04)
    block_size_le = Reader(buf,False).get_u32(0x04)
    big_endian = (block_size_be < block_size_le)
    sdt.seek(0)


    # hold files from interleaved data inside sdt
    streams = {}
    counts = {}

    # read all blocks until end
    offset = 0
    while (offset < sdt_size):
        # read new block header
        header = Reader(sdt.read(0x10), big_endian)
        block_type   = header.get_u32(0x00)
        block_size   = header.get_u32(0x04)
        block_empty  = header.get_u32(0x08)
        block_id     = header.get_u32(0x0c)
        
        if block_type != 0x00 and block_size < 0x10:
            print("ERROR: bad block size at %08x" % (offset))
            return 1

        if block_type == 0x00:  # padding after file end
            #print("skip 0x10 at %08x" % (offset))
            sdt.seek( offset + 0x10 )

        elif block_type == 0xF0:  # file end control
            # current file end
            for block_id in streams:
                size = os.path.getsize(streams[block_id].name)
                streams[block_id].close()
                if size == 0:
                    #streams[block_id].close()
                    #os.remove(streams[block_id].name)
                    pass
                counts[block_id] += 1
                #print("file end %08x at %08x" % (block_id, offset))

            streams = {}
            #if offset + block_size < sdt_size:
            #    print("WARN: data left after %08x" % (offset))
            #break

            pass

        elif block_type == 0x10:  #file start control
            write_block = True

            #print("register %08x at %08x" % (block_id, offset))
            if block_id in streams:
                print("stream id %08x not closed at %08x" % (block_id, offset))
                return 1

            # ignore non-selected types
            current_type    = (block_id >>  0) & 0x0000FFFF
            current_subtype = (block_id >> 16) & 0x0000FFFF
            if filter_type    >= 0 and filter_type    != current_type:
                write_block = False
            if filter_subtype >= 0 and filter_subtype != current_subtype:
                write_block = False

                
            # register (open) a new file to write data in later blocks
            if write_block:
                if not block_id in counts:
                    counts[block_id] = 0
                subfile_num = counts[block_id]

                path = basedir + '/' + basename + '/'
                
                try:
                    os.makedirs(path)
                except:
                    pass

                path += basename
                if is_dat:
                    path += "_%04i" % (total_files)
                elif subfile_num > 0:
                    path += "_%04i" % (subfile_num)
                total_files += 1

                path += get_extension(block_id)
                print("created: %s" % (os.path.split(path)[1]))

                streams[block_id] = open(path, "wb")

        else:
            write_block = True
            stream_has_data = False
            
            current_type    = (block_type >>  0) & 0x0000FFFF
            current_subtype = (block_type >> 16) & 0x0000FFFF

            if block_type in streams:
                stream_has_data = streams[block_type].tell() != 0

            # ignore non-selected types
            if filter_type    >= 0 and filter_type     != current_type:
                write_block = False
            if filter_subtype >= 0 and filter_subtype != current_subtype:
                write_block = False

            #if current_type not in (0x01, 0x20, 0x02) and block_id == 0 and stream_has_data:
            #    print("type %08x with padding at %08x" % (block_type, offset))
                
            # some audio blocks have padding that must be skipped,
            # but first block has always "id" 0 and must be written
            if (block_type in padding_type_map and 
                block_id == 0 and stream_has_data):
                write_block = False


            # unassigned block data, should have registered it first
            if write_block and block_type not in streams:
                print("ERROR: stream id %08x unregistered at %08x (doesn't use blocks?)" % (block_type, offset))
                return 1

            # write block data to registered stream
            if write_block:
                streams[block_type].write( sdt.read(block_size - 0x10) )
            else:
                sdt.seek( offset + block_size )

        offset = sdt.tell()

    # clean up
    sdt.close()

    return 0

def main(argv=sys.argv, argc=len(sys.argv)):

    if argc < 2:
        print("Usage: %s file [type filter] [subtype filter]" % argv[0])
        print("  Type/subtypes are int values where 0x01 is audio")
        return 1

    sdt_path = os.path.realpath(argv[1])
    if not os.path.isfile(sdt_path):
        print("invalid path")
        return 1
    
    filter_type = -1
    if argc >= 3:
        filter_type = int(argv[2], 0)
    filter_subtype = -1
    if argc >= 4:
        filter_subtype = int(argv[3], 0)

    extract_sdt(sdt_path, filter_type, filter_subtype)
    
if __name__ == "__main__":
    main()
