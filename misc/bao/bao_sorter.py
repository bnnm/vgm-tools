# ###################################################################
# BAO SORTER 
# ###################################################################
 
# moves all usable file BAOs in src to dst
# stream BAOs are normally in a separate dir (ok if it's the same)
# can be run multiple times, detects BAOs already moved

import glob
import os
import fnmatch
import struct

import os, shutil

cfg_ext = ''
cfg_fname_in = '*' + cfg_ext
cfg_recursive = False

cfg_src_mem_path = '.'       #where memory BAOs (BAO_0x...) are
cfg_dst_mem_path = '.\\ok'      #where memory BAOs (BAO_0x...) go
cfg_src_str_path = '.'       #where stream BAOs (Common_BAO_0x...) are
cfg_dst_str_path = '.\\ok'      #where stream BAOs (Common_BAO_0x...) go



# #############################################################################

def find_files_recursive(dir, pattern, recursive):
    files = []
    for root, dirnames, filenames in os.walk(dir):
        for filename in fnmatch.filter(filenames, pattern):
            files.append(os.path.join(root, filename))

        if not recursive:
            break
    return files

class ReaderHelper(object):
    def __init__(self, file):
        self.file = file
        self.be = False

    def set_be(self, be):
        self.be = be

    def get_u32le(self, offset):
        self.file.seek(offset)
        return struct.unpack('<I', self.file.read(4))[0]

    def get_u32be(self, offset):
        self.file.seek(offset)
        return struct.unpack('>I', self.file.read(4))[0]

    def get_s32le(self, offset):
        self.file.seek(offset)
        return struct.unpack('<i', self.file.read(4))[0]

    def get_s32be(self, offset):
        self.file.seek(offset)
        return struct.unpack('>i', self.file.read(4))[0]

    def get_s32(self, offset):
        if self.be:
            return self.get_s32be(offset)
        else:
            return self.get_s32le(offset)

    def get_u32(self, offset):
        if self.be:
            return self.get_u32be(offset)
        else:
            return self.get_u32le(offset)

    def get_size(self):
        self.file.seek(0, os.SEEK_END); 
        return self.file.tell()


class BaoHelper(object):
    version = 0
    classtype = 0
    type = 0
    external_id = 0
    is_stream = 0
    chain_count = 0
    chain = []
    parse_ok = False

    def __init__(self, fname, sub=False):
        self.fname = fname
        self.sub = sub

        if not os.path.isfile(fname):
            return #already moved

        file = open(fname,"rb")
        reader = ReaderHelper(file)
        self.parse(reader)
        file.close()

    def parse(self, reader):
        self.parse_ok = False

        basename = os.path.basename(fname)
        pos = basename.rfind('.')
        if not (pos == -1 or basename.endswith(".bao")):
            return #not bao
    

        self.version = reader.get_u32be(0x00) & 0x00FFFFFF
        if   self.version == 0x001b0100: 
            #Assassin's Creed
            self.is_namefix = True
            cfg_base_entry              = 0xA4
            cfg_o_class                 = 0x20
            cfg_o_header_id             = 0x28+0x00
            cfg_o_type                  = 0x28+0x04
            cfg_o_audio_external_id     = 0x28+0x1c
            cfg_o_audio_external_flag   = 0x28+0x28
            cfg_o_audio_prefetch_size   = 0x28+0x74
            cfg_o_layer_external_id     = 0x28+0x4c
            cfg_o_layer_external_flag   = 0x28+0x2c
            cfg_o_layer_prefetch_size   = 0x28+0x50
            cfg_o_sequence_chain_count  = 0x28+0x2c
            cfg_o_sequence_chain_entry  = 0x14
        elif self.version == 0x001F0010:
            #Prince of Persia 2008
            self.is_namefix = False
            cfg_base_entry              = 0xA4
            cfg_o_class                 = 0x20
            cfg_o_header_id             = 0x28+0x00
            cfg_o_type                  = 0x28+0x04
            cfg_o_audio_external_id     = 0x28+0x1c
            cfg_o_audio_external_flag   = 0x28+0x28
            cfg_o_audio_prefetch_size   = 0x28+0x74
            cfg_o_layer_external_id     = 0x28+0x00
            cfg_o_layer_external_flag   = 0x28+0x2c
            cfg_o_layer_prefetch_size   = 0x28+0x50
            cfg_o_sequence_chain_count  = 0x28+0x2c
            cfg_o_sequence_chain_entry  = 0x14
        elif self.version == 0x0025010A or self.version == 0x0025011D: 
            #Prince of Persia: The Forgotten Sands
            #Shaun White Skateboarding
            self.is_namefix = False
            cfg_base_entry              = 0xB4
            cfg_o_class                 = 0x20
            cfg_o_header_id             = 0x28+0x00
            cfg_o_type                  = 0x28+0x04
            cfg_o_audio_external_id     = 0x28+0x24
            cfg_o_audio_external_flag   = 0x28+0x2c
            cfg_o_audio_prefetch_size   = 0x28+0x78
            cfg_o_layer_external_id     = 0x28+0x00
            cfg_o_layer_external_flag   = 0x28+0x30
            cfg_o_layer_prefetch_size   = 0x28+0x54
            cfg_o_sequence_chain_count  = 0x28+0x34
            cfg_o_sequence_chain_entry  = 0x14
        else:
            return #not bao #raise ValueError("unknown BAO version " + hex(self.version))
        
        be_check = reader.get_u32be(cfg_o_class)
        if (be_check & 0xFF000000) != 0:
            is_be = True
        elif (be_check & 0x000000FF) != 0:
            is_be = False
        else:
            raise ValueError("unknown endian")
        reader.set_be(is_be)

        if self.version == 0x0025011D and not is_be:
            cfg_base_entry          = 0xB0

            
        self.classtype = reader.get_u32(cfg_o_class)
        if self.classtype & 0x0FFFFFFF != 0:
            raise ValueError("unknown class " + hex(self.classtype))
        
        if self.classtype != 0x20000000:
            return

        #detect extra PC/Wii size
        if reader.get_size() > cfg_base_entry:
            field = reader.get_s32(cfg_base_entry)
            if field == 0 or field == -1 or field == 1:
                cfg_base_entry += 0x04

        self.header_id = reader.get_u32(cfg_o_header_id)
        self.type      = reader.get_u32(cfg_o_type)
        if   self.type == 0x01:
            self.external_id = reader.get_u32(cfg_o_audio_external_id)
            self.is_stream   = reader.get_u32(cfg_o_audio_external_flag)
            self.is_prefetch = reader.get_u32(cfg_o_audio_prefetch_size)

        elif self.type == 0x06:
            self.external_id = reader.get_u32(cfg_o_layer_external_id)
            self.is_stream   = reader.get_u32(cfg_o_layer_external_flag)
            self.is_prefetch = reader.get_u32(cfg_o_layer_prefetch_size)

        elif self.type == 0x05:
            self.chain_count = reader.get_u32(cfg_o_sequence_chain_count)
            self.chain = []
            for i in range(0, self.chain_count):
                #print("chain " +str(i)+ " at " + str(cfg_base_entry + i*cfg_o_sequence_chain_entry))
                chain_id = reader.get_u32(cfg_base_entry + i*cfg_o_sequence_chain_entry)
                #print("chain id "+ str(chain_id)+ ", " +str(i)+ " at " + str(cfg_base_entry + i*cfg_o_sequence_chain_entry))
                self.chain.append(chain_id)

        elif self.type == 0x08:
            self.external_id = 0
            self.is_stream = 0
            self.is_prefetch = 0

        else:
            print("found type " + self.type + " in " + self.fname)
            return

        self.parse_ok = True
 
    def get_basepath(self, path):
        basepath = os.path.dirname(path)
        if   basepath.startswith(cfg_src_mem_path):
            basepath = basepath[len(cfg_src_mem_path):]
        elif basepath.startswith(cfg_src_str_path):
            basepath = basepath[len(cfg_src_str_path):]
        elif basepath.startswith(cfg_dst_mem_path):
            basepath = basepath[len(cfg_dst_mem_path):]
        elif basepath.startswith(cfg_dst_str_path):
            basepath = basepath[len(cfg_dst_str_path):]
        else:
            raise ValueError("unknown path in '" + basepath + "'")
        basepath += "\\"
        return basepath

 
    #find memory or stream BAO, that may be moved or not (src or dst dirs) 
    def find_bao(self, bao_id, is_src):

        if is_src:
            base_cfg = cfg_src_mem_path
        else:
            base_cfg = cfg_dst_mem_path
        basepath = self.get_basepath(self.fname)
        basename = "BAO_0x{:08x}{}".format(bao_id, cfg_ext)

        dir_name = base_cfg + basepath + basename
        #print("try exists " + dir_name)
        if os.path.isfile(dir_name):
            #print("find BAO found: " + dir_name)
            return dir_name

        #print("BAO not found")
        return "" #possibly voices


    def move_file(self, fname_src, fname_dst):
        #print("move_file: " + fname_src + " to " + fname_dst)

        if not os.path.isfile(fname_src):
            return #already moved
        if os.path.isfile(fname_dst):
            return #already moved

        if fname_src == fname_dst:
            return #already moved

        #print("move_file ok")
        #return
            
        try:
            basepath = os.path.dirname(fname_dst)
            os.makedirs(basepath)
        except OSError as exception:
            pass

        #may complain about already moved files, meh
        try:
            os.rename(fname_src,fname_dst)
        except:
            pass
        #shutil.move(fname_src,fname_dst)
        
    #move base BAO, which is always a memory one
    def move_self(self):
        #print("move_self1")
        fname_src = self.fname

        #print("move_self2")
        basepath = self.get_basepath(fname_src)
        basename = os.path.basename(fname_src)
        fname_dst = cfg_dst_mem_path + basepath + basename

        self.move_file(fname_src, fname_dst)

    #move companions BAO, which can be memory or stream or both
    def move_others(self):
        valid = False #not valid if didn't find companions
        valid_stream = False

        if self.is_namefix:
            prefetch_id = (self.external_id & 0x0FFFFFFF) | 0x30000000;
            stream_id = self.external_id
        else:
            prefetch_id = self.external_id
            stream_id = self.external_id

        if self.is_stream != 0:
            basepath = "\\" #streams are in a simple dir
            basename = "Common_BAO_0x{:08x}{}".format(stream_id, cfg_ext)

            src_name = cfg_src_str_path + basepath + basename
            dst_name = cfg_dst_str_path + basepath + basename

            if os.path.isfile(src_name) or os.path.isfile(dst_name):
                self.move_file(src_name, dst_name)
                valid = True

        if self.is_prefetch != 0 and self.header_id != stream_id:
            basepath = self.get_basepath(self.fname)
            basename = "BAO_0x{:08x}{}".format(prefetch_id, cfg_ext)
           
            src_name = cfg_src_mem_path + basepath + basename
            dst_name = cfg_dst_mem_path + basepath + basename
            
            if os.path.isfile(src_name) or os.path.isfile(dst_name):
                self.move_file(src_name, dst_name)
                #prefetch with stream must have moved stream first stream
                if self.is_stream != 0 and valid:
                    valid = True
                else: #happens with voices
                    print("ignoring prefetch BAO without stream " + self.fname)
           
        if self.is_prefetch == 0 and self.is_stream == 0:
            basepath = self.get_basepath(self.fname)
            basename = "BAO_0x{:08x}{}".format(stream_id, cfg_ext)

            src_name = cfg_src_mem_path + basepath + basename
            dst_name = cfg_dst_mem_path + basepath + basename

            if os.path.isfile(src_name) or os.path.isfile(dst_name):
                self.move_file(src_name, dst_name)
                valid = True
        
        return valid

    def move(self):
        if not self.parse_ok:
            return
        
        #print("*MOVE: " + self.fname)

        if   self.type == 0x01 or self.type == 0x06:
            #print("move 01/06")
            moved = self.move_others()
            if moved:
                self.move_self()
            else:
                print("ignoring non-useful BAO: " + self.fname)
            
 
        elif self.type == 0x05:
            #print("move 05")

            print("sequence BAO: " + self.fname)
            if self.sub:
                raise ValueError("unexpected sequence in sequence")

            bao_ok = 0
            bao_chain = []
            # see if all parse ok
            for chain_id in self.chain:
                is_src = True
                fname_chain = self.find_bao(chain_id, is_src)
                if fname_chain == "":
                    is_src = False
                    fname_chain = self.find_bao(chain_id, is_src)

                if fname_chain == "": #probably not extracted (ex. 1ch)
                    print("ignored sequence, chain BAO not found")
                    return

                bao = BaoHelper(fname_chain, True)
                if not bao.parse_ok:
                    raise ValueError("unexpected bad sequence BAO " + fname_chain)

                if bao.type == 0x08:
                    print("silence BAO in sequence " + self.fname)
                else:
                    bao_ok += 1
                    
                if is_src:
                    bao_chain.append(bao)

            #we don't want sequences of silences only
            if bao_ok == 0:
                return

            #move all (including possible silences, otherwise they won't move)
            for bao in bao_chain:
                bao.move()
            self.move_self()

        elif self.type == 0x08:
            #print("move 08")

            #we only want silences inside sequences
            if not self.sub:
                return
            print("moved type08") #uncommon
            self.move_self()
            

        else:
            raise ValueError("unexpected move type")

# #############################################################################

fnames = find_files_recursive(cfg_src_mem_path, cfg_fname_in, cfg_recursive)
for fname in fnames:
    try:
        #print("check: " + fname)
        bao = BaoHelper(fname)
        bao.move()

    except Exception as e:
        print("Error in " + fname + ":")
        print(e)
#print("end")
