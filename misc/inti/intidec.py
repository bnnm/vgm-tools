# decrypts Inti Creates engine files
#
# some info inti_encdec tool: https://forum.xentax.com/viewtopic.php?f=32&t=23816
# this script is similar to the above tool but this allows using free keys 
# and supports file table decryption used in the latest games
#
# for long hashes hash-renamer.py + filelists in 
# for short filenames, hash is unknown but names are previsible and 
# c4f76749, 85b3c32d/b845e4c2, 4ddd7369 seem to be the "sound"/"group"/"stream"/etc folders
#
# HOW TO FIND LIST-BIN
# - newer games have a giant filename<>id list that is used to decrypt files
# - we need to locate the real start of this list so it can be used to decrypt
# - the list is basically a binary minidatabase embedded in the exe (it's referred internally as a type of 'list')
# - currently there are 2 list formats but they should be autodetected
# - tips to find them (needs a hex editor):
#   - it's useful to look at previous games' exes list first (offset listed in the help below) so you know it looks
#   - then look for "Common/" or other dir name or file (the list includes "path/file" strings)
#   - now go back from that point and see if you find the list header
#     - along the way there should be a long list of 0x10 entries in this format:
#       00: hash/id
#       04: number or FFFFFFFF 
#       08: FFFFFFFF
#       0c: number
#       (beware as they don't need to be 32-bit aligned)
#     - then other list that is mostly 0s
#     - if you reach lists of strings or other structures like the above, you are past the header
#   - header has values and offsets (see parse_list_gg/gv below) so it shouldn't be hard to manually check the exact start
#     - gg usually looks like: "0C000000 08000000 NNNNNNNN 30000000"
#     - gv usually looks like: "NNNNNNNN NNNNNNNN NNNNNNNN NNNNNNNN 20000000"
#       - where NN are usually lowish numbers, little endian
#   - note this list format is used for multiple things to make sure the header you found is for the filelist
#   - if going back fails, try decompiling (IDA/Ghidra/etc) and see offsets near the filenames
# - apart from the list decryption needs a base key, but it's usually "(blah).oss" so easy to find
#   - or use strings2.exe and check simple/suspicious strings
#   - or decompile and see decryption calls
# - do note that the filenames are hashed, but in list-bin follow the original order
#   (IOW: use them to make an ordered playlist, ex. */4ddd7369/* = ordered streams)


import os, sys, argparse, glob, struct, zlib

class Cli(object):
    def __init__(self):
        self.list_map = {} #path > list of id
        self.list_map_file = {} #basename > list of id
        self.curr_file = None
        self.size_excess = 0
        pass

    def parse(self):
        description = (
            "decrypts Inti Creates files\nSome files are double-encrypted and need multiple passes, see below for known cases"
        )

        # some known keys from inti_encdec tool (recent games only use snd* and obj* plus list-bin)
        epilog = (
            "examples (files not always encrypted):\n"
            "%(prog)s *.bigrp -k snd90270\n"
            "- get all files that start with bgm_ and end with .ogg\n"
            "%(prog)s ./Data/**/* -lb game.exe -lo 0x10AE030 -k BSM3.oss \n"
            "- decrypts latest games based on ID per file on exe + extra key\n"
            "  (some files need a second pass)"

            "\nKnown keys:\n"
            " (2 keys listed means 2 passes with each key)\n"
            " (list-bin ID is an internal ID from that list;\n"
            "  you need to pass the offset to said list and the suffix key)\n"
            " - Common\n"
            "   - snd90210: *.bisar, *.bigrp (not compressed)\n"
            "   - obj90210: *.osb files (usually compressed)\n"
            "   - bft90210: *.bfb files (sometimes compressed)\n"
            "   - set90210: *.stb (not compressed)\n"
            "   - scroll90210: *.scb (usually compressed)\n"
            "   - txt20170401: *.ttb (compressed)\n"
            "   - x4NKvf3U: *.tb2 (compressed)\n"
            "   - ssbpi90210: ?\n"
            " - Bloodstained COTM1/2\n"
            "   - gYjkJoTX / zZ2c9VTK: system/saves? (offset 0x10)\n"
            "   - gVTYZ2jk / JoTXzc9K: system/saves? (offset 0x10)\n"
            " - Dragon Marked for Death\n"
            "   - gVTYZ2jk + (playerID) / JoTXzc9K + (playerID): saves?\n"
            " - Gal Gun Returns (PC)\n"
            "   - (list-bin ID) + /GGR.oss: 'game.exe' offset:\n"
            "     * 0x9CDAD0 (PC)\n"
            " - Luminous Avenger iX 2 (PC)\n"
            "   - (list-bin ID) + /gva2.oss: 'game.exe' offset:\n"
            "     * 0x14A18B0 (PC)\n"
            "   - gva2encrypt_key_01 / gva2encrypt_key_02: saves? (offset ?)\n"
            " - Blaster Master Zero 3\n"
            "   - (list-bin ID) + /BSM3.oss: 'game.exe' offset:\n"
            "     * 0x10AE030 (PC)\n"
            "   - r8Z5Zrn5 / mn7FuW57: saves? (offset 0x10)\n"
            "   - mn7FuW57 / r8Z5Zrn5: saves? (offset 0x10)\n"
            " - Gunvolt 3\n"
            "   - (list-bin ID) + /GV3.oss: 'main' offset:\n"
            "     * 0x17CB879 (Switch) [after decompression]\n"
            "   - gv3encrypt_key_01 / gv3encrypt_key_02: saves? (offset 0x400)\n"
            " - Grim Guardians / Gal Guardians\n"
            "   - (list-bin ID) + /ggac.oss: 'main' offset:\n"
            "     * 0x11F538C (Switch) [after decompression]\n"
            " - YOHANE THE PARHELION -BLAZE in the DEEPBLUE- Demo\n"
            "   - (list-bin ID) + /yhn.oss: 'main' offset:\n"
            "     * 0x008EE260 (PC)\n"
            "\n"
            "   * after decrypting with list-bin, some files need a second common key\n"
            "     (usually snd90210 and bft90210)\n"
            "   * exes may include list-bin tables for other platforms"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument("files", help="files to match (accepts wildcards)", nargs="+")
        p.add_argument("-k","--key", help="key to use")
        p.add_argument("-o","--offset", help="offset to use", )
        p.add_argument("-lb","--list-bin", help="decryption file table binary (combined with key)")
        p.add_argument("-lo","--list-offset", help="decryption file table offset")
        p.add_argument("-z","--zip", help="decompress files", action="store_true")
        p.add_argument("-ni","--name-id", help="adds id to name for list-bin files", action="store_true")
        self.args = p.parse_args()

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
        if start != 0x0c or entry != 0x08 or count != 3:
            raise ValueError("unknown list-bin2 format or wrong offset %x" % (offset))
        
        table2_offset, = struct.unpack_from("<I", data, offset + start + 0x08)
        table3_offset, = struct.unpack_from("<I", data, offset + start + 0x10)
        names_offset = offset + table3_offset
        offset += table2_offset

        # table2 :
        # 00: table info (start, entry, count)
        # 0c: hash?

        start, entry, items = struct.unpack_from("<III", data, offset)
        if start != 0x0c or entry != 0x2c:
            raise ValueError("unknown list-bin2 format or wrong offset %x" % (offset))

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
        elif test00 == 0x0c and test04 == 0x08 and test0c == 0x30:
            self.parse_list_gg(data, offset)
        else:
            raise ValueError("unknown table format")

    def get_ids(self):
        if not self.args.list_bin:
            return
    
        file = self.curr_file
        file = os.path.realpath(file)
        file = file.replace('\\', '/')
        basename = os.path.basename(file)

        ids = None
        for path in self.list_map.keys():
            if file.endswith(path):
                ids = self.list_map[path]
                break

        if not ids:
            if basename in self.list_map_file:
                ids = self.list_map_file[basename]
        if not ids:
            raise ValueError("list-bin id not found")

        return ids
        
    def get_string_key(self):
        # external key (varies per file type)
        # key could be reused for N files if list_bin isn't used but og code does redo it every time anyway
        key = self.args.key

        # in some games files are pre-encrypted per file using an internal ID,
        # and have table in the exe with id<>file name. find this ID based on the filename.
        # (after decrypting like this files need a second decryption with a standard key)
        if self.curr_id:
            if key[0] == '/':
                key = key[1:]
            key = "%08x/%s" % (self.curr_id, key)
            #print(key)

        return key

    def get_base_key(self, str_key):
        key = 0xA1B34F58CAD705B2
        for c in str_key:
            val = ord(c)
            key = (key + val) * 141 
            key = key & 0xFFFFFFFFFFFFFFFF

        return key


    def decrypt(self, data):
        str_key = self.get_string_key()
        if not str_key:
            return False

        key = self.get_base_key(str_key)

        start = 0
        if self.args.offset:
            start = int(self.args.offset, 0)

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
            #print("can't zlib", e)
            return None

    def is_bigrp(self, data):
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
        if self.is_bigrp(data):
            return "bigrp"
        return None

    def process_subfile(self, data):
    
        done = self.decrypt(data)
        if not done:
            raise ValueError("couldn't decrypt (no key?):")


        data_unzip = self.decompress(data)
        if data_unzip:
            data = data_unzip

        
        file = self.curr_file
        file_ext = os.path.splitext(file)[1]
        base_name = os.path.basename(file)
        base_path = os.path.dirname(file)
        if not base_path:
            base_path = '.'


        out_ext = None
        if not file_ext:
            out_ext = self.autodetect_ext(data)
        if not out_ext:
            out_ext = "dec"
        
        if self.curr_id:
            if self.curr_index is not None:
                if self.args.name_id:
                    file_out = "%s_%03i_%08x.%s" % (file, self.curr_index, self.curr_id, out_ext)
                else:
                    file_out = "%s_%03i.%s" % (file, self.curr_index, out_ext)
            else:
                if self.args.name_id:
                    file_out = "%s_%08x.%s" % (file, self.curr_id, out_ext)
                else:
                    file_out = "%s.%s" % (file, out_ext)
        else:
            file_out = "%s.%s" % (file, out_ext)

        with open(file_out, 'wb') as f:
            f.write(data)


    def process_file(self):
        file = self.curr_file
        if not os.path.isfile(file):
            #print("not a file: " + file)
            return

        with open(file, 'rb') as f:
            data = bytearray(f.read())

        self.curr_id = None
        items = self.get_ids()
        if items:
            for i, item in enumerate(items):
                id, offset, size = item
                
                if not size: #dir?
                    continue

                self.curr_id = id
                self.curr_index = i
                if len(items) == 1:
                    if size != len(data) and size + self.size_excess != len(data):
                        #size = len(data)
                        raise ValueError("expected size doesn't match file size (exp=%x, len=%x)" % (size, len(data)))
                    self.curr_index = None

                subdata = data[offset : offset + size]
                self.process_subfile(subdata)
        else:
            self.process_subfile(data)

        print("done:", file)

    def main(self): 
        self.parse()
        if not self.args:
            return

        # target files
        files = []
        for file in self.args.files:
            files += glob.glob(file, recursive=True)

        if not files:
            print("no valid files found")
            return

        # file decryption
        if not self.args.key:
            print("key not specified")
            return

        self.parse_list()

        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in ['.py','.exe','.dec','.bat'] or file.endswith('main'):
            #if file.endswith('.py') or file.endswith('.exe') or file.endswith('.dec') or file.endswith('main'):
                continue

            self.curr_file = file
            
            try:
                self.process_file()
            except ValueError as e:
                print("error in %s: %s" % (file, str(e)))

if __name__ == "__main__":
    Cli().main()
