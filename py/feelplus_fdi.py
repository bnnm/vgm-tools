# feelplus .fpi + .fpd extractor by bnnm
#
# found in Lost Odyssey (X360), No More Heroes (PS3/X360), Ninety-Nine Nights II (X360)
# loosely based on original .bms by chrrox, thanks to hcs for figuring out the name encoding.
# 
# TODO add extensions for Lost Odyssey (unknown exts table<>file)

import os, struct, argparse, glob


class Reader:
    def __init__(self, data, big_endian=False):
        self.data = data
        self.big_endian = big_endian
        self.base_endian = big_endian
        self.offset = 0
        self.offsets = []
    
    def set_endian(self, be):
        self.big_endian = be

    def back_endian(self):
        self.big_endian = self.base_endian

    def skip(self, size):
        self.offset += size

    def goto(self, offset):
        self.offset = offset

    def curr(self):
        return self.offset
    
    def save(self):
        self.offsets.append(self.offset)
    
    def back(self):
        self.offset = self.offsets.pop(0)

    def read(self, fmt, size):
        v = struct.unpack_from(fmt, self.data, self.offset)
        self.offset += size
        return v

    def u32(self):
        fmt = '>I' if self.big_endian else '<I'
        return self.read(fmt, 4)[0]

    def u16(self):
        fmt = '>H' if self.big_endian else '<H'
        return self.read(fmt, 2)[0]

    def u8(self):
        return self.read('B', 1)[0]

class FpNames:
    DICT = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_./".lower() #may use CAPS in some games (LO=lower)
    DICT_LEN = 40

    def __init__(self, r, names_offset, encoded_size=True):
        self._r = r
        self._noff = names_offset #start of names in file
        self._names_encode_size = encoded_size #if name encode size in the first value

    # based on hcs's code: https://gist.github.com/hcs64/84b530e2becc5b0420f54e9767c39b6a
    def _unpack_name(self):
        r = self._r

        # same as file's endianness (.fpi, old xse: LE, new xwv, new xse: BE)
        #r.set_endian(self.names_big_endian)

        name = ''
        num_words = 0
        max_words = None
        read_word = True

        while True:
            if read_word and max_words is not None and num_words > max_words:
                break;

            if read_word:
                read_word = False
                v = r.u16()
                num_words += 1

            if v == 0:
                read_word = 1
                continue

            x = v % self.DICT_LEN
            v = (v - x) // self.DICT_LEN
            if self._names_encode_size and max_words is None:
                max_words = x
                continue
            name += self.DICT[x]

        #r.back_endian()
        return name

    def decode(self, name_offset):
        r = self._r
        r.save()

        # name offsets are halved
        pos = self._noff + name_offset * 2
        r.goto(pos)
        name = self._unpack_name()

        r.back()
        return name

# container
class FpObject:
    def __init__(r):
        pass


class App:

    def __init__(self, r, args):
        self.r = r
        self.args = args

    def get_pack(self, curr):
        #slow but meh
        best = None
        for pack in self.packs:
            if curr < pack.files_offset:
                break
            best = pack
        return best
    
    #buggy
    def get_folder_req(self, file):
        if not file:
            return ''

        name = file.name
        folder = self.get_folder_req(file.parent)
        if not folder:
            folder = file.pack.basedir

        return folder + '/' + name

    def get_folder_seq(self, file):
        path = []
        curr_file = file
        while curr_file:
            path.append(curr_file.name)
        
            if curr_file.parent_entry < 0:
                path.append(file.pack.basedir)
                break
           
            parent = curr_file.pack.files[curr_file.parent_entry]
            if parent == curr_file:
                print("bad", parent.pos, file.pack.fpdfile)
                raise ValueError("pad parent_entry")
            curr_file = parent

        path.reverse()
        return '/'.join(path)

    def get_path(self, file):
        # gets (pack-name)/(file-path)/(file-path)/.../(file-leaf)

        read_files_recursive = self.args.recursive
        if read_files_recursive:
            name = self.get_folder_req(file)
        else:
            name = self.get_folder_seq(file)
        if self.args.uppercase:
            name = name.upper()
        return name
        

    def start(self):
        r = self.r

        read_files_recursive = self.args.recursive
        print_base = False or self.args.list
        print_exts = False or self.args.list
        print_packs = False or self.args.list
        print_files = False or self.args.list

        # read main header
        base = self.read_base()
        self._names = FpNames(r, base.names_offset)

        self.base = base
        self.exts = []
        self.packs = []
        self.files = []
        self.exts = []

        # read exts (there may be a better way to calc size, not sure)
        r.goto(base.exts_offset)
        for i in range(base.exts_max):
            ext = self.read_ext()
            ext.pos = i
            self.exts.append(ext)

        # read .fpd packs info
        r.goto(base.packs_offset)
        for i in range(base.packs_max):
            pack = self.read_pack()
            pack.pos = i
            self.packs.append(pack)

        # read files recursive (buggy/unfinished but maybe faster)
        if read_files_recursive:
            for pack in self.packs:
                self.read_pack_files(pack)

        # read files sequentially
        if not read_files_recursive:
            prev_section = None
            pos = None
            r.goto(base.files_offset)
            for i in range(base.files_max):
                file = self.read_file()

                pack = self.get_pack(file.curr)
                if prev_section != pack.files_offset:
                    prev_section = pack.files_offset
                    pos = 0
                file.pack = pack
                file.pos = pos
                pack.files.append(file)
                
                self.files.append(file)

                #print("%s %04x (%08x): o=%08x s=%08x pc=%04x,%04x>%04x  u=%04x,%04x  %s" % (pack.basedir, pos, file.curr, file.offset, file.size, file.parent_entry, file.child_entry, file.child_count, file.unk0, file.unk1, file.name))
                pos += 1
        self.files.sort(key=lambda x: (x.pack.pos, x.pos))

        if print_base:
            print("base (%08x): packs=%08x>%04x, files=%08x>%04x, names=%08x, exts=%08x" % (base.curr, base.packs_offset, base.packs_max, base.files_offset, base.files_max, base.names_offset, base.exts_offset))

        if print_exts:
            for ext in self.exts:
                print("ext %02x (%08x): %s" % (ext.pos, ext.curr, ext.name))

        if print_packs:
            for pack in self.packs:
                print("pack %02x (%08x): files=%08x>%04x, name=%s:%s" % (pack.pos, pack.curr, pack.files_offset, pack.root_files, pack.fpdfile, pack.basedir))

        if print_files:
            for file in self.files:
                print("%s %04x (%08x): o=%08x s=%08x pc=%04x,%04x>%04x  u=%04x,%04x  %s" % (file.pack.fpdfile, file.pos, file.curr, file.offset, file.size, file.parent_entry, file.child_entry, file.child_count, file.unk0, file.unk1, self.get_path(file)))


        if not self.args.list:
            self.extract_files()

    def read_base(self):
        r = self.r

        o = FpObject()
        o.curr = r.curr()

        #0x00
        o.id = r.u32() #empty
        r.u32() #empty
        r.u32() #version?
        r.u16() #unk
        r.u16() #head size / start
        if o.id != 0:
            raise ValueError("unknown format")

        #0x10
        r.u32() #10: id/version?
        o.disc_num = r.u8()
        o.disc_max = r.u8()
        r.u16() #?
        r.u16() #?
        o.packs_max = r.u16() #entry per .fpd
        o.files_max = r.u32() #for all .fpd

        # 0x20
        o.packs_offset = r.u32() #base pack info
        o.files_offset = r.u32() #file info (packs also point)
        o.names_offset = r.u32() #table with all names
        o.exts_offset  = r.u32() #table with exts (unsure how are referenced)

        # better way?
        o.exts_max = (o.files_offset - o.exts_offset) // 2

        #0x30+: data start
        
        return o

    def read_ext(self):
        r = self.r

        o = FpObject()
        o.curr = r.curr()

        o.ext_noff = r.u16()
        o.name = self._names.decode(o.ext_noff)

        return o

    def read_pack(self):
        r = self.r

        o = FpObject()
        o.curr = r.curr()

        #0x00
        disc_cur = r.u8() #same as disc_num
        r.u8() #0/1
        o.root_files = r.u16()
        o.files_offset = r.u32() #main section offset
        size1 = r.u32() #size left until tbl_names_offset?
        size2 = r.u32() #size left until tbl_start_offset?

        #0x10
        r.u32() #null
        o.basedir_noff = r.u16() #name offset for the default dir of this .fpd
        r.u16() #always 0x1000?
        o.fpdfile_noff = r.u16() #name offset for this pack's name
        r.u16() #always 0x1000?
        r.u32() #crc-like (repeated in other fpi)

        #0x20
        r.u32() #some value? (usually 0x40000000, 0 on first)
        r.u32() #null
        r.u32() #null
        r.u32() #null

        o.basedir = self._names.decode(o.basedir_noff)
        o.fpdfile = self._names.decode(o.fpdfile_noff)
        o.files_offset += o.curr

        o.files = []
        return o

    def read_file(self):
        r = self.r

        o = FpObject()
        o.curr = r.curr()

        #0x00
        o.name_noff = r.u16() #name for this file/diroffset for the default dir of this .fpd
        o.unk0 = r.u16() #flags? (not name offset)
        r.u32() #hash?
        o.offset_flags = r.u32()
        o.parent_entry = r.u16() #from root entry pos (+1)
        o.child_count =  r.u16() #some count/size (not name offset)

        #0x10
        o.size = r.u32()
        o.child_entry = r.u16() #fixed to 16 if file (ignore)
        o.unk1 = r.u16() #? (dir only)

        o.offset = o.offset_flags & 0x00FFFFFF #upper 2 bits = flag
        if o.offset_flags & 0x80000000:
            o.offset *= 0x800
        if o.offset_flags & 0x08000000: #no difference?
            o.offset *= 0x800
        if o.offset_flags & 0x01000000:
            pass #some model files in nmh x360, no apparent diffs

        # not seen
        if o.offset_flags & 0x36000000:
            print("unknown flag %08x at %x" % (o.offset_flags & 0x36000000, o.curr))

        o.is_external = o.offset_flags & 0x40000000 #in filesystem
        o.is_file = o.offset or o.size
        o.name = self._names.decode(o.name_noff)

        o.parent_entry -= 1 # -1 = root

        o.pack = None #for filenames
        o.parent = None #for filenames
        o.files = []
        return o


    def read_pack_files(self, pack):
        r = self.r

        #read current pack's subfiles/folder
        r.save()
        r.goto(pack.files_offset)
        for i in range(pack.root_files):
            print("pack %02x (%08x): files=%08x>%04x, name=%s:%s" % (pack.pos, pack.curr, pack.files_offset, pack.root_files, pack.fpdfile, pack.basedir))
            subfile = self.read_file()
            subfile.pack = pack
            subfile.parent = None
            subfile.pos = i
            pack.files.append(subfile)

            self.read_subfiles(subfile, pack.files_offset)
        r.back()

    def read_subfiles(self, file, root_offset):
        r = self.r
        print("%s %04x (%08x): o=%08x s=%08x pc=%04x,%04x>%04x  u=%04x,%04x  %s" % (file.pack.fpdfile, file.pos, file.curr, file.offset, file.size, file.parent_entry, file.child_entry, file.child_count, file.unk0, file.unk1, self.get_path(file)))

        self.files.append(file)
        if file.is_file: #current file is leaf (not a folder)
            return

        start_pos = file.child_entry
        subfile_offset = root_offset + start_pos * 0x18

        #read current pack's subfiles/folder
        r.save()
        r.goto(subfile_offset)
        for i in range(file.child_count):
            subfile = self.read_file()
            subfile.pack = file.pack
            subfile.parent = file
            subfile.pos = start_pos + i
            file.files.append(subfile)

            self.read_subfiles(subfile, root_offset)
        r.back()

    def extract_files(self):
        input_files = {}
        total = 0
        files_done = {} #files that point to same offset (just in case)
        names_done = {} #files with different offset/size but same name
        try:
            for file in self.files:
                if not file.is_file or file.is_external:
                    continue

                # get final name
                fpd = file.pack.fpdfile
                outbase_dir = self.args.outdir
                if outbase_dir is None:
                    outbase_dir = os.path.splitext(fpd)[0]
                path = outbase_dir + '/' + self.get_path(file)

                # filters
                if self.args.filter_packs:
                    if fpd.lower() not in map(str.lower, self.args.filter_packs):
                        #print("skip pack %s" % (path))
                        continue
                if self.args.filter_exts:
                    ext = os.path.splitext(path)[1]
                    if not ext or ext[1:].lower() not in map(str.lower, self.args.filter_exts):
                        #print("skip ext %s" % (path))
                        continue


                # not seen but just in case
                key = (file.pack.pos, file.offset, file.size)
                if key in files_done:
                    print("ignoring dupe %s" % (path))
                files_done[key] = True

                # happens in LO
                if path in names_done:
                    base, ext = os.path.splitext(path)
                    path = "%s[%05i]%s" % (base, file.pos, ext)
                    #print("renamed dupe %s" % (path))
                names_done[path] = True

                # open fpd if needed
                input_fpd = input_files.get(fpd)
                if input_fpd is None:
                    try:
                        input_fpd = open(fpd, 'rb')
                    except:
                        input_fpd = False
                    input_files[fpd] = input_fpd
                if input_fpd is False:
                    print("pack file %s not found, ignoring %s" % (fpd, path))
                    continue
                input_fpd.seek(file.offset)
                data = input_fpd.read(file.size)

                try:
                    dirname = os.path.dirname(path)
                    os.makedirs(dirname)
                except:
                    pass
                    
                with open(path, 'wb') as fo:
                    fo.write(data)

                print("wrote %s" % (path))
                total += 1

            print("done, total %i" % (total))
        finally:
            for input_file in input_files.values():
                if input_file is not False:
                    input_file.close()

def test_name(self, r, offset):
    tbl_names_offset = 0x55C90
    names = FpNames(r, tbl_names_offset)
    print(names.decode(offset))


def handle_file(args, file):
    ext = os.path.splitext(file)[1]
    if not file.lower().endswith('.fpi'):
        raise ValueError("File is not a .fpi")

    max = os.path.getsize(file)
    if max > 0x200000:
        raise ValueError("File too big to be a .fpi")
    with open(file, 'rb') as f:
        data = f.read()

    r = Reader(data, big_endian=False)
    App(r, args).start()


def main(args):
    if True:
    #try:
        files = []
        for file_glob in args.files:
            files += glob.glob(file_glob)

        if not files:
            raise ValueError("no files found")
    
    
        for file in files:
            #try:
                handle_file(args, file)
            #except Exception as e:
            #    print("error processing %s: %s" % (file, e))

    #except Exception as e:
    #    print("error: %s" % (e))

def parse_args():
    description = (
        "Extract feelplus's .fpi archives"
    )
    epilog = None

    ap = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", help="files to match", nargs='*', default=["*.fpi"])
    ap.add_argument("-l","--list", help="list info only", action='store_true')
    ap.add_argument("-fp","--filter-packs", help="only extract files inside .fpd packs", nargs='+')
    ap.add_argument("-fe","--filter-exts", help="only extract files that end with these extensions", nargs='+')
    #ap.add_argument("-r","--recursive", help="read files recursively (unfinished)", action='store_true')
    ap.add_argument("-u","--uppercase", help="filenames should be uppercase (x360=lower, PS3=upper)", action='store_true')
    ap.add_argument("-o","--outdir", help="output dir (default: auto, use . for current)", default=None)

    args = ap.parse_args()
    args.recursive = False
    return args

if __name__ == "__main__":
    args = parse_args()
    main(args)
    #test_name(r, 0x15A7)
