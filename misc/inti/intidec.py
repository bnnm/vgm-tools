# Decrypts Inti Creates's ICE engine files.
#
# Usage (older games)
#   intidec.py *.bigrp -k (game key)
#
# Usage (newer games):
#   intidec.py Data/**/* -lb (game exe) -a
# (for switch games game exe is 'main' and must be decompressed with nsnsotool or such)
#
# If the above fails to autodetect (or throws many decryption errors), read huge comment below and try again:
#   intidec.py Data/**/* -lb (game exe) -lo (offset to decryption list inside exe) -k (game key)
#
# ---
#
# To rename files with hashed folders/names (Data/c4f76749/85b3c32d/...) use inti-renamer.py + names.txt
#
# Some info from inti_encdec: https://forum.xentax.com/viewtopic.php?f=32&t=23816
#
# ---
#
# HOW TO FIND OFFSET TO DECRYPTION LIST INSIDE EXE (A.K.A LIST-BIN)
# - newer games have a giant filename<>id list + key that is used to decrypt files
# - the list is a binary minidatabase inside the exe (internally called a type of 'list')
# - we need to locate the start of this list, so it can be used to decrypt
# - currently there are 2 list formats but they should be autodetected
#
# Known offsets + keys: intidec.py -h
# Or try autodetect: intidec.py -ab (game exe)
#
# If that fails the list can be found manually fairly easily (needs a hex editor):
# - it's useful to look at known games' exes list + offsets (intidec.py -h) so you know it looks
# - list-bin is made of: table0 + table1 + table2 + file-paths
# - use hex editor's "find" to look for "Common/" string, or a similar dir name/file (file-paths)
#   - exes may include list-bin tables for other platforms
# - now find *backwards* hex integer FFFFFFFF, this should be table2's last entry
# - scrolling upwards there should be a long list of 0x10 entries in this format:
#     00: hash/id
#     04: low number or FFFFFFFF
#     08: low number or FFFFFFFF
#     0c: number
#   (beware as they don't need to be 32-bit aligned)
# - keep going backwards until table2 starts (no more entries in that format)
# - then there is other table1 that is mostly 0s, that can be in 2 formats
# - go backwards until table1 starts, then also table0 right before it:
#   - list_gg usually starts like: "0C000000 08000000 NNNNNNNN NN000000" (NN000000 is a sub-offset to table1)
#   - list_gv usually starts like: "NNNNNNNN 20000000 NNNNNNNN NNNNNNNN"
#     (where NN are usually lowish numbers, little endian)
#   - save the exact starting offset to use later
# - if you reach lists of strings or other structures like the above, you are past the header
# - note this list format is used for multiple things so make sure offset you found is for the filelist
# - if going back fails, try decompiling (IDA/Ghidra/etc) and see offsets near the filenames
# 
# Apart from the list decryption needs a base key, but it's usually "(game-id).oss" so easy to find
# - find ".oss" in hex editor, should be first entry
# - or use strings2.exe and check simple/suspicious strings
# - or decompile and see decryption calls
#
# Now use intidec.py **/* -lb (game exe) -lo (offset to decryption list found above) -k (base key)
#
# Do note that the filenames are hashed, but in binary list-bin follow the original order
# (IOW: use them to make an ordered playlist, ex. */4ddd7369/* = ordered streams)


import os, sys, argparse, glob, struct, zlib, pathlib, re

DEFAULT_EXTENSION = 'bin'
IGNORED_EXTENSIONS = ['.py','.exe','.bat','.sh', '.tar','.zip','.7z']
IGNORED_FILES = ['main']

#class IgnoredError(Exception):
#    pass

class Decryptor(object):

    def __init__(self, args):
        self.list_map = {} #path > list of id
        self.list_map_file = {} #basename > list of id
        self.size_excess = 0
        self.args = args

    def get_cstring_size(self, data, offset):
        size = 0
        while True:
            if data[offset] == 0:
                break
            size += 1 #no need for the null
            offset += 1
        return size

    # gunvolt3
    def parse_list_gv(self, data, offset):
        # format:
        # 00: files
        # 04: table2 entry size?
        # 08: table1 offset (id info?)
        # 0c: table2 offset (files)
        # 10: table3 offset (names)
        # 14: data

        items, = struct.unpack_from("<I", data, offset + 0x00)
        value20, = struct.unpack_from("<I", data, offset + 0x04)
        if items > 0x10000 or value20 != 0x20:
            raise ValueError("unknown list-bin format or wrong offset %x" % (offset))

        table2_offset, = struct.unpack_from("<I", data, offset + 0x0c)
        table3_offset, = struct.unpack_from("<I", data, offset + 0x10)
        names_offset = offset + table3_offset
        offset += table2_offset

        for i in range(items):
            # table2 entry:
            # 00: ID (matches BIGRP internal ID)
            # 04: null
            # 08: name offset
            # 0c: some ID?
            # 10: start offset
            # 14: file size (partial if file has sub-files, each its own ID, 0 if directory)
            # 18: 0/1 flag
            # 1c: file attributes/flags?

            # get ids + name offsets
            id,             = struct.unpack_from("<I", data, offset + 0x00)
            path_offset,    = struct.unpack_from("<I", data, offset + 0x08)
            data_offset,    = struct.unpack_from("<I", data, offset + 0x10)
            data_size,      = struct.unpack_from("<I", data, offset + 0x14)

            path_offset += names_offset
            path_size = self.get_cstring_size(data, path_offset)
            path = data[path_offset : path_offset + path_size].decode('utf-8')
            #todo other fields list dir/type?


            item = (id, data_offset, data_size)

            # build map of path > id (not sure if filename is unique but dirs aren't)
            if path not in self.list_map:
                self.list_map[path] = []
            self.list_map[path].append(item)

            # just in case of moved files without full paths allow base filename too
            basename = os.path.basename(path)
            if basename not in self.list_map_file:
                self.list_map_file[basename] = []
            self.list_map_file[basename].append(item)

            offset += 0x20

    # grim/gal guardians
    def parse_list_gg(self, data, offset):
        # info format (at the start of a table):
        # 00: start offset 
        # 04: entry size
        # 08: count
        
        # table0:
        # 00: table1 offset (id info?)
        # 04: table1 size
        # 08: table2 offset (files)
        # 0c: table2 size
        # 10: table3 offset (names)
        # 14: table3 size

        self.size_excess = 0x08 #regular files are padded by 0x08 of unknown data at the end (some hash?)

        start, entry, count = struct.unpack_from("<III", data, offset)
        #if start != 0x0c or entry != 0x08 or count != 3:
        #    raise ValueError("unknown list-bin2 format or wrong offset %x" % (offset))
        
        table2_offset, = struct.unpack_from("<I", data, offset + start + 0x08)
        table3_offset, = struct.unpack_from("<I", data, offset + start + 0x10)
        names_offset = offset + table3_offset
        offset += table2_offset

        # table2 :
        # 00: table info (start, entry, count)
        # 0c: hash?

        start, entry, items = struct.unpack_from("<III", data, offset)
        #if start != 0x0c or entry != 0x2c:
        #    raise ValueError("unknown list-bin2 format or wrong offset %x" % (offset))

        offset += start + 0x04
        for i in range(items):
            # table2 entry:
            # 00: 0x1BB / 0
            # 04: ID (matches BIGRP internal ID)
            # 08: null
            # 0c: ? offset
            # 10: name offset
            # 14: some ID?
            # 18: start offset
            # 1c: file size? (partial if file has sub-files, each its own ID, 0 if directory)
            # 20: 0/1 flag
            # 24: flags
            # 28: file attributes/flags?

            # get ids + name offsets
            id,             = struct.unpack_from("<I", data, offset + 0x04)
            path_offset,    = struct.unpack_from("<I", data, offset + 0x10)
            data_offset,    = struct.unpack_from("<I", data, offset + 0x18)
            data_size,      = struct.unpack_from("<I", data, offset + 0x1c)

            path_offset += names_offset
            path_size = self.get_cstring_size(data, path_offset)
            path = data[path_offset : path_offset + path_size].decode('utf-8')
            #todo other fields list dir/type?

            item = (id, data_offset, data_size)

            # build map of path > id (not sure if filename is unique but dirs aren't)
            if path not in self.list_map:
                self.list_map[path] = []
            self.list_map[path].append(item)

            # just in case of moved files without full paths allow base filename too
            basename = os.path.basename(path)
            if basename not in self.list_map_file:
                self.list_map_file[basename] = []
            self.list_map_file[basename].append(item)

            offset += entry

    def parse_list(self):
        if not self.args.list_bin:
            # earlier files don't have list-bin
            return

        with open(self.args.list_bin, 'rb') as f:
            data = f.read()

        offset = 0
        if self.args.list_offset:
            offset = int(self.args.list_offset, 0)

        # these tables are reused for varios things but we need the id/path table
        test00, test04, test08, test0c = struct.unpack_from("<IIII", data, offset + 0x00)
        if test04 == 0x20:
            self.parse_list_gv(data, offset)
        elif test00 == 0x0c and test04 == 0x08 and test0c >= 0x30 and test0c <= 0x100: #0x30: common, 0x40: GV Trilogy
            self.parse_list_gg(data, offset)
        else:
            raise ValueError("unknown table format")


    def hash_string(self, bstr):
        hash = 0xCDE723A5
        for i in range(len(bstr)):
            temp = (hash + bstr[i]) & 0xffffffff
            hash = (141 * temp) & 0xffffffff

        return format(hash, "08x")

    # convert blah/blah.
    def hash_filepath(self, file):
        parts = []

        for part in file.split('/'):
            if not bool(re.fullmatch(r"[0-9a-f]{8}", part)):
                bstr = part.encode('utf-8')
                part = self.hash_string(bstr)
            parts.append(part)
        return '/'.join(parts)

    def _get_ids_fullname(self, file):
        for path in self.list_map.keys():
            if file.endswith(path):
                return self.list_map[path]
        return None

    def _get_ids_basename(self, file):
        basename = os.path.basename(file)
        if basename in self.list_map_file:
            return self.list_map_file[basename]
        return None

    # try to find ids associated to current file (1 id for single files or N for packs).
    # exe has exact paths to file, but for flexibility try different formats
    # since file may be moved, try to find 
    def get_ids(self, file):
        if not self.args.list_bin:
            return None

        #file = os.path.realpath(file)
        file = file.replace('\\', '/')
        hash = self.hash_filepath(file)
        for item in [file, hash]:
            ids = self._get_ids_fullname(item)
            if ids:
                return ids
        
            ids = self._get_ids_basename(item)
            if ids:
                return ids
        
        #if len(basename) != 8 and '.' in basename:
        #    raise IgnoredError("file may not be encrypted")
        raise ValueError("list-bin id not found")

    def get_string_key(self, curr_id):
        # external key (varies per file type)
        # key could be reused for N files if list_bin isn't used but og code does redo it every time anyway
        key = self.args.key

        # in some games files are pre-encrypted per file using an internal ID,
        # and have table in the exe with id<>file name. find this ID based on the filename.
        # (after decrypting like this files need a second decryption with a standard key)
        if curr_id:
            if key[0] == '/':
                key = key[1:]
            key = "%08x/%s" % (curr_id, key)

        return key

    def get_base_key(self, str_key):
        key = 0xA1B34F58CAD705B2
        for c in str_key:
            val = ord(c)
            key = (key + val) * 141 
            key = key & 0xFFFFFFFFFFFFFFFF

        return key


    def decrypt(self, data, curr_id):
        str_key = self.get_string_key(curr_id)
        if not str_key:
            return False

        key = self.get_base_key(str_key)

        start = 0
        if self.args.decryption_offset:
            start = int(self.args.decryption_offset, 0)

        for i in range(start, len(data)):
            val = data[i];
            data[i] = val ^ ((key >> (i & 0x1F)) & 0xFF);

            key = (key + val) * 141 
            key = key & 0xFFFFFFFFFFFFFFFF

        return True

    def decompress(self, data):
        if not self.args.zip:
            return None

        try:
            usize, = struct.unpack_from("<I", data, 0x00)
            #decompress = zlib.decompressobj(-zlib.MAX_WBITS)
            #inflated = decompress.decompress(data, 0x04)
            #inflated += decompress.flush()
            #return inflated

            udata = zlib.decompress(data[0x04:], 15)
            if len(udata) != usize:
                print("unexpected zlib size") #shouldn't happen
                return None
            return udata
        except:
            #print("can't zlib")
            return None

    def _is_bigrp(self, data):
        header_size, = struct.unpack_from("<I", data, 0x00)
        entry_size, = struct.unpack_from("<I", data, 0x04)
        subsongs, = struct.unpack_from("<I", data, 0x08)
        
        if header_size == 0x10:
            dummy, = struct.unpack_from("<I", data, 0x0c)
            codec, = struct.unpack_from("<I", data, 0x18)
            if entry_size != 0x40 or dummy != 0x00:
                return False

        elif header_size == 0x0c:
            codec, = struct.unpack_from("<I", data, 0x14)
            if entry_size != 0x34:
                return False
            
        else:
            return False

        if subsongs > 1000 or codec > 0x03:
            return False

        return True
        

    def autodetect_ext(self, data):
        if self._is_bigrp(data):
            return "bigrp"
        return None

    def process_subfile(self, data, file, curr_id, curr_index):

        done = self.decrypt(data, curr_id)
        if not done:
            raise ValueError("couldn't decrypt (no key?):")

        data_unzip = self.decompress(data)
        if data_unzip:
            data = data_unzip

        
        base_ext = os.path.splitext(file)[1]
        base_name = os.path.basename(file)
        base_path = os.path.dirname(file)
        if not base_path:
            base_path = '.'

        # detect decrypting subfiles already renamed, like GROUP_COMMON.sndGrp
        file_ext = base_ext
        if curr_index is not None:
            file_ext = None

        out_ext = None
        if not file_ext:
            out_ext = self.autodetect_ext(data)
        if not out_ext:
            out_ext = DEFAULT_EXTENSION
        
        if curr_id:
            # Newer method with decryption ID, which is the hash of a full path.
            # Add it to filename in certain cases, as it can be used to reverse/rename later:
            show_id = False
            if curr_index is not None:
                show_id = True # file is a pack, and the ID contains the internal filename
            if self.args.no_name_id:
                show_id = False

            # the double __ for subfiles is meant to make renaming a bit easier
            if curr_index is not None:
                if show_id:
                    file_out = "%s__%04i~%08x.%s" % (file, curr_index, curr_id, out_ext)
                else:
                    file_out = "%s__%04i.%s" % (file, curr_index, out_ext)
            else:
                if show_id:
                    file_out = "%s~%08x.%s" % (file, curr_id, out_ext)
                else:
                    file_out = "%s.%s" % (file, out_ext)
        else:
            if base_ext:
                # for simple files/keys with an extension
                file_out = "%s" % (file)
            else:
                file_out = "%s.%s" % (file, out_ext)

        if curr_index is not None:
            print('pack: %s' % file_out)

        # could avoid decrypting/decompressing but woulnd't detect extension
        if self.args.list:
            return

        if self.args.dir:
            file_out = self.args.dir + '/' + file_out
            path = pathlib.Path(file_out)
            path.parent.mkdir(parents=True, exist_ok=True)
            
        with open(file_out, 'wb') as f:
            f.write(data)


    def process_file(self, file):
        if not os.path.isfile(file):
            #print("not a file: " + file)
            return

        with open(file, 'rb') as f:
            data = bytearray(f.read())

        # find id(s) associated to current file (different than the filename).
        # Packs have N ids per subfile, which is the full hashed path including the subfile
        # pack's subfile id: SoundAssets_QON_GROUP_COMMON_sndGrp_QON_JGL_GAMEOVER_bigrp
        # path: SoundAssets/QON_GROUP_COMMON.sndGrp + QON_JGL_GAMEOVER.bigrp

        items = self.get_ids(file)
        if items:
            # list-bin decryption
            for i, item in enumerate(items):
                id, offset, size = item
                
                if not size: #dir?
                    continue

                curr_id = id 
                curr_index = i #subfile index
                if len(items) == 1:
                    if size != len(data) and size + self.size_excess != len(data):
                        #size = len(data)
                        raise ValueError("expected size doesn't match file size (exp=%x, len=%x)" % (size, len(data)))
                    curr_index = None

                subdata = data[offset : offset + size]
                self.process_subfile(subdata, file, curr_id, curr_index)
        else:
            # regular decryption
            self.process_subfile(data, file, None, None)

        print("done:", file)


class Autodetector(object):
    def __init__(self, args):
        self.args = args

    def _find_list(self, data):
        MINUS = b'\xFF\xFF\xFF\xFF'


        # find filelist
        index = data.find(b'Common/')
        if index <= 0:
            return
        filelist_end = index
        #print("filelist: %08x " % (filelist_end))

        # find table2's end
        index = data.rfind(MINUS, 0, index)
        if index <= 0:
            return

        # align to table2's entry
        offset = index - 0x08
        if data[offset - 0x04 : offset] == MINUS:
            offset -= 0x04
        table2_end = offset + 0x10

        # find table2's start, knowing that entries always look like this:
        #  00: hash/id
        #  04: low number or FFFFFFFF
        #  08: low number or FFFFFFFF
        #  0c: number
        max_low = 0x80 # MJG uses ~0x18
        while offset > 0:
            hash, num1, num2, pos = struct.unpack_from("<IiiI", data, offset)

            if num1 > max_low or num2 > max_low or num1 == 0 and num2 == 0 and pos == 0:
                break
            offset -= 0x10

        if offset == 0:
            return

        table2_start = offset + 0x10
        table2_size = table2_end - table2_start #approximate
        print("table2: %08x > %08x (~%08x)" % (table2_start, table2_end, table2_size))

        # find table1's start, knowing that entries always look like this:
        # #TODO: may not work with list_gv
        # 00: low number (starts with 0x0C)
        # 04: offset?
        # 08: low number
        # 0c: offset?
        max_low1 = 0x800
        max_low2 = 0x8000
        max_offset = 0xFFFFFF
        offset = table2_start - 0x100 # approximate
        while offset > 0:
            num1, offset1, num2, offset2 = struct.unpack_from("<iiii", data, offset)

            if num1 > max_low1 or num2 > max_low2 or offset1 > max_offset or offset2 > max_offset:
                break

            # some are dummy entries
            #if num1 == 0 and num2 == 0 and offset1 == 0 and offset1 == 0:
            #    break

            offset -= 0x10

        if offset == 0:
            return
        
        for test_offset in [offset - 0x20, offset - 0x10, offset]:
        
            # before table1 there is a mini header, where the offset we need starts
            test00, test04, test08, test0c = struct.unpack_from("<IIII", data, test_offset)
            if test00 == 0x0c and test04 == 0x08: # and test0c in (0x30, 0x40): #0x40: GV Trilogy
                print(f"-lo 0x{test_offset:08x}")
                return test_offset

        print(f"-lo (possibly around {offset - 0x20:08x})")


    def _find_key(self, data):
        suffix = b'.oss'

        end_index = data.find(suffix)
        index = data.rfind(b'\x00', 0, end_index)
        if index <= 0:
            return
            
        key = data[index + 1: end_index + len(suffix)]
        try:
            key = key.decode('utf-8')
            print('-k ' + key)
            return key
        except:
            return
            pass

    def process(self):
        exe = self.args.list_bin
        if not exe:
            print('game exe not specified')
            return

        with open(exe, 'rb') as f:
            data = f.read()

        offset = self._find_list(data)
        key = self._find_key(data)

        if offset:
            self.args.list_offset = '0x%08x' % (offset)
        else:
            print("-lo (not found)")

        if key:
            self.args.key = key
        else:
            print("-k (not found)")
# ---

def parse():
    description = (
        "Decrypts Inti Creates's ICE engine files"
    )

    # some known keys from inti_encdec tool (recent games only use snd* and obj* plus list-bin)
    epilog = (
        "Decrypts Inti Creates's ICE engine files.\n"
        "\n"
        "Older games need various keys, hardcoded in the exe (see below)\n"
        "- %(prog)s *.bigrp -k snd90270\n"
        "\n"
        "Newer games need a decryption table in the exe\n"
        "%(prog)s ./Data/**/* -lb game.exe -a\n"
        "%(prog)s ./Data/**/* -lb game.exe -lo 0x10AE030 -k BSM3.oss \n"
        "  (some files need a second pass with -k (key) to decrypt after the above)\n"
        "\n"
        "Known keys:\n"
        " - Common\n"
        "   * -k snd90210 **/*.bisar **/*.bigrp  #not compressed\n"
        "   * -k obj90210 **/*.osb  #usually compressed\n"
        "   * -k bft90210 **/*.bfb  #sometimes compressed\n"
        "   * -k set90210 **/*.stb  #not compressed\n"
        "   * -k scroll90210 **/*.scb  #usually compressed\n"
        "   * -k txt20170401 **/*.ttb  #compressed\n"
        "   * -k x4NKvf3U **/*.tb2   #compressed\n"
        "   * -k ssbpi90210 #?\n"
        " - Bloodstained COTM1/2\n"
        "   * -k gYjkJoTX / zZ2c9VTK -do 0x10  #system/saves?\n"
        "   * -k gVTYZ2jk / JoTXzc9K -do 0x10  #system/saves?\n"
        " - Dragon Marked for Death\n"
        "   * -k gVTYZ2jk + {playerID} / JoTXzc9K + {playerID}  #saves?\n"
        " - Gal Gun Returns\n"
        "   * -lb game.exe -lo 0x009CDAD0 -k GGR.oss \n"
        " - Luminous Avenger iX 2\n"
        "   * -k gva2encrypt_key_01 / gva2encrypt_key_02 -do 0x10  #saves?\n"
        "   * -lb game.exe -lo 0x014A18B0 -k gva2.oss \n"
        " - Blaster Master Zero 3\n"
        "   * -k r8Z5Zrn5 / mn7FuW57: saves? (-do 0x10)\n"
        "   * -lb game.exe -lo 0x010AE030 -k BSM3.oss \n"
        " - Gunvolt 3\n"
        "   * -k gv3encrypt_key_01 / gv3encrypt_key_02 -do 0x400 #saves?\n"
        "   * -lb main-dec -lo 0x017CB879 -k GV3.oss \n"
        " - Grim Guardians / Gal Guardians: Demon Purge\n"
        "   * -lb main-dec -lo 0x011F538C -k ggac.oss \n"
        " - Yohane the Parhelion -BLAZE in the DEEPBLUE- Demo\n"
        "   * -lb game.exe -lo 0x008EE260 -k yhn.oss \n"
        " - PuzzMix\n"
        "   * -lb eboot.bin -lo 0x007d19d0 -k RRG.oss Data/**/* \n"
        " - Umbraclaw\n"
        "   * -lb game.exe -lo 0x011a9f70 -k QON.oss Data/**/* \n"
        " - Card-en-Ciel Demo\n"
        "   * -lb game.exe -lo 0x00E3E560 -k RCG.oss \n"
        " - Card-en-Ciel\n"
        "   * -lb game.exe -lo 0x00F09140 -k RCG.oss \n"
        " - Gal Guardians: Servants of the Dark\n"
        "   * -lb game.exe -lo 0x01978a20 -k: ggac2.oss \n"
        " - Gunvolt Trilogy Enhanced\n"
        "   * -lb game.exe  -lo 0x0040A280 -k GVFSP.oss Data0/**/* \n"
        "   * -lb game1.exe -lo 0x005E42C0 -k GV1.oss Data1/**/* \n"
        "   * -lb game2.exe -lo 0x006dc380 -k GV2.oss Data2/**/* \n"
        "   * -lb game3.exe -lo 0x0149b800 -k GV3.oss Data3/**/* \n"
        "   * -lb game4.exe -lo 0x0112bc80 -k GV3.oss Data3/**/* \n"
        "\n"
        " Two keys listed means 2 passes with each key.\n"
        " After decrypting with list-bin, some files need a second common key\n"
        "  (usually snd90210 and bft90210)\n"
        " Other than .bigrp most formats aren't autodetected and use .bin extension"
    )

    p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("files", help="files to match (accepts wildcards)", nargs="*", default=["Data/**/*"])
    p.add_argument("-l", "--list", help="list info instead of decrypting", action="store_true")
    p.add_argument("-do", "--decryption-offset", help="offset where to start decryption (needed for few files)")
    p.add_argument("-k", "--key", help="key to decrypt files")
    p.add_argument("-lb","--list-bin", help="decryption table binary file (combined with key)")
    p.add_argument("-lo","--list-offset", help="decryption table offset in list-bin")
    p.add_argument("-Ni","--no-name-id", help="don't write internal id in pack for list-bin files", action="store_true")
    p.add_argument("-z", "--zip", help="decompress files (slower)", action="store_true")
    p.add_argument("-d", "--dir", help="base output dir", default='_out')
    p.add_argument("-a", "--autodetect", help="autodetect list-bin offset and key", action="store_true")
    args = p.parse_args()
    return args

def main():
    args = parse()
    if not args:
        return

    if args.autodetect:
        Autodetector(args).process()
        #return

    # target files
    files = []
    for file in args.files:
        files += glob.glob(file, recursive=True)

    if not files:
        print("no valid files found")
        return

    # always needs some key
    if not args.key:
        print("key not specified (see help)")
        return

    # setup decryptor
    dec = Decryptor(args)
    dec.parse_list()

    for file in files:
        ext = os.path.splitext(file)[1]
        if ext in IGNORED_EXTENSIONS or file in IGNORED_FILES:
            continue
        # allow decrypting with standard keys (2nd pass) but only if no list-bin was used
        if ext == '.' + DEFAULT_EXTENSION:
            if args.list_bin or args.autodetect:
                continue
        
        try:
            dec.process_file(file)
        #except IgnoredError as e:
        #    pass
        except ValueError as e:
            print("error in %s: %s" % (file, str(e)))

if __name__ == "__main__":
    main()
