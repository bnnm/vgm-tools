# makes a .bat renamer from .acb+awb (put together first)
# - finds references to .awb in .acb
# - reads .awb info and matches their original filename, based on that
import glob, struct, os, hashlib, pathlib, argparse, fnmatch

REN_LOWER = False


#TODO with repeats this may happen:
#  00clone.awb
#  blah.acb
#  blah.awb
# generates:
#  REM ren blah.acb blah.acb
#  ren 00clone.awb blah.awb         !!can't rename since blah.awb exists
#  ren blah.awb blah[1].awb         !!but will be renamed here

#------------------------------------------------------------------------------
import struct

# from vgmstream's cri_utf.c, mostly migrated as-is from C
class CriUtf():
    UTF_MAX_SCHEMA_SIZE         = 0x8000    # arbitrary max

    COLUMN_BITMASK_FLAG         = 0xf0
    COLUMN_BITMASK_TYPE         = 0x0f

    COLUMN_FLAG_NAME            = 0x10     # column has name (may be empty)
    COLUMN_FLAG_DEFAULT         = 0x20     # data is found relative to schema start (typically constant value for all rows)
    COLUMN_FLAG_ROW             = 0x40     # data is found relative to row start
    COLUMN_FLAG_UNDEFINED       = 0x80     # shouldn't exist

    COLUMN_TYPE_UINT8           = 0x00
    COLUMN_TYPE_SINT8           = 0x01
    COLUMN_TYPE_UINT16          = 0x02
    COLUMN_TYPE_SINT16          = 0x03
    COLUMN_TYPE_UINT32          = 0x04
    COLUMN_TYPE_SINT32          = 0x05
    COLUMN_TYPE_UINT64          = 0x06
    COLUMN_TYPE_SINT64          = 0x07
    COLUMN_TYPE_FLOAT           = 0x08
    COLUMN_TYPE_DOUBLE          = 0x09
    COLUMN_TYPE_STRING          = 0x0a
    COLUMN_TYPE_VLDATA          = 0x0b
    COLUMN_TYPE_UINT128         = 0x0c # for GUIDs
    COLUMN_TYPE_UNDEFINED       = -1

    COLUMN_TYPES_NAMES = {
        COLUMN_TYPE_UINT8    : 'u8',
        COLUMN_TYPE_SINT8    : 's8',
        COLUMN_TYPE_UINT16   : 'u16',
        COLUMN_TYPE_SINT16   : 's16',
        COLUMN_TYPE_UINT32   : 'u32',
        COLUMN_TYPE_SINT32   : 's32',
        COLUMN_TYPE_UINT64   : 'u64',
        COLUMN_TYPE_SINT64   : 's64',
        COLUMN_TYPE_FLOAT    : 'flt',
        COLUMN_TYPE_DOUBLE   : 'dbl',
        COLUMN_TYPE_STRING   : 'str',
        COLUMN_TYPE_VLDATA   : 'dat',
        COLUMN_TYPE_UINT128  : '128',
        COLUMN_TYPE_UNDEFINED: 'und',
    }

    class CriUtfResult():
        def __init__(self):
            self.type = 0
            self.value = None

    class CriUtfColumn():
        def __init__(self):
            self.flag = 0
            self.type = 0
            self.name = None
            self.offset = 0

        def __repr__(self):

            if self.flag & CriUtf.COLUMN_FLAG_UNDEFINED:
                flag = 'UND'
            elif self.flag & CriUtf.COLUMN_FLAG_DEFAULT:
                flag = 'CON'
            elif self.flag & CriUtf.COLUMN_FLAG_ROW:
                flag = 'ROW'
            else:
                flag = 'UNK'

            type = CriUtf.COLUMN_TYPES_NAMES.get(self.type, '?')

            name = self.name
            if name is None:
                name = '(null)'

            return f"{flag:<3} {type:<3}  {name}"

    class CriUtfContext():
        def __init__(self):
            self.data = None
            self.table_offset = 0

            # header
            self.table_size = 0
            self.version = 0
            self.rows_offset = 0
            self.strings_offset = 0
            self.data_offset = 0
            self.name_offset = 0
            self.columns = 0
            self.row_width = 0
            self.rows = 0
            
            self.schema_buf = None
            self.schema = []

            # derived
            self.schema_offset = 0
            self.schema_size = 0
            self.rows_size = 0
            self.data_size = 0
            self.strings_size = 0
            self.string_table = None
            self.table_name = ''


    def __init__(self, data, table_offset=0):
        self.rows = 0
        self.columns = 0
        self.name = None
        self._utf = None
        self._open(data, table_offset)
        pass
    
    def _get(self, format, data, offset):
        out,  = struct.unpack_from(format, data, offset)
        return out
        
    def get_s8(self, data, offset):
        return self._get('>b', data, offset)
    
    def get_u8(self, data, offset):
        return self._get('>B', data, offset)

    def get_u16be(self, data, offset):
        return self._get('>H', data, offset)

    def get_s16be(self, data, offset):
        return self._get('>h', data, offset)

    def get_u32be(self, data, offset):
        return self._get('>I', data, offset)

    def get_s32be(self, data, offset):
        return self._get('>i', data, offset)

    def get_u64be(self, data, offset):
        return self._get('>Q', data, offset)

    def get_s64be(self, data, offset):
        return self._get('>q', data, offset)

    def get_f32be(self, data, offset):
        return self._get('>f', data, offset)

    def get_zstring(self, data, pos):
        end = pos
        while True:
            if data[end] == 0:
                break
            end += 1
        return data[pos:end]


    def _open(self, data, table_offset):
        utf = CriUtf.CriUtfContext()
        self._utf = utf
    
        utf.data = data
        utf.table_offset = table_offset

        buf = data[table_offset : table_offset + 0x20]

        if buf[0:4] != b'@UTF':
            raise ValueError('@UTF: not a CRI UTF table')

        utf.table_size     = self.get_u32be(buf, 0x04) + 0x08
        utf.version        = self.get_u16be(buf, 0x08)
        utf.rows_offset    = self.get_u16be(buf, 0x0a) + 0x08
        utf.strings_offset = self.get_u32be(buf, 0x0c) + 0x08
        utf.data_offset    = self.get_u32be(buf, 0x10) + 0x08
        utf.name_offset    = self.get_u32be(buf, 0x14) # within string table
        utf.columns        = self.get_u16be(buf, 0x18)
        utf.row_width      = self.get_u16be(buf, 0x1a)
        utf.rows           = self.get_u32be(buf, 0x1c)

        utf.schema_offset  = 0x20
        utf.schema_size    = utf.rows_offset - utf.schema_offset
        utf.rows_size      = utf.strings_offset - utf.rows_offset
        utf.strings_size   = utf.data_offset - utf.strings_offset
        utf.data_size      = utf.table_size - utf.data_offset

        # 00: early (32b rows_offset?), 01: +2017 (no apparent differences) */
        if utf.version != 0x00 and utf.version != 0x01:
            raise ValueError("@UTF: unknown version")


        if utf.table_offset + utf.table_size > len(data):
            raise ValueError("Error")
        if utf.rows_offset > utf.table_size or utf.strings_offset > utf.table_size or utf.data_offset > utf.table_size:
            raise ValueError("Error")
        if utf.strings_size <= 0 or utf.name_offset > utf.strings_size:
            raise ValueError("Error")
        # no rows is possible for empty tables (have schema and columns names but no data) [PES 2013 (PC)] 
        if utf.columns <= 0: #or utf.rows <= 0 or utf.rows_width <= 0:
            raise ValueError("Error")
        if utf.schema_size >= CriUtf.UTF_MAX_SCHEMA_SIZE:
            raise ValueError("Error")

        # load sections (unneeded since it's all in memory but to simplify porting original code)

        # schema section: small so keep it around (useful to avoid re-reads on column values) 
        utf.schema_buf = data[utf.table_offset + utf.schema_offset : utf.table_offset + utf.schema_offset + utf.schema_size]

        # row section: skip, mid to big (0x10000~0x50000) so not preloaded for now 

        # string section: low to mid size but used to return c-strings 
        utf.string_table = data[utf.table_offset + utf.strings_offset : utf.table_offset + utf.strings_offset + utf.strings_size]

        # data section: skip (may be big with memory AWB) 

        #------------------------------------------------
        #--- schema

        column_offset = 0
        schema_pos = 0

        utf.table_name = self.get_zstring(utf.string_table, utf.name_offset).decode('utf-8')

        utf.schema = [None] * utf.columns

        for i in range(utf.columns):
            utf.schema[i] = CriUtf.CriUtfColumn()
        
            info = self.get_u8(utf.schema_buf, schema_pos + 0x00)
            name_offset = self.get_u32be(utf.schema_buf, schema_pos + 0x01)

            if name_offset > utf.strings_size:
                raise ValueError("Error")
            schema_pos += 0x01 + 0x04

            utf.schema[i].flag = info & CriUtf.COLUMN_BITMASK_FLAG
            utf.schema[i].type = info & CriUtf.COLUMN_BITMASK_TYPE
            utf.schema[i].name = None
            utf.schema[i].offset = 0

            # known flags are name+default or name+row or name+default+row, though no name is apparently possible
            if (utf.schema[i].flag == 0 or
                not (utf.schema[i].flag & CriUtf.COLUMN_FLAG_NAME) or
                 (utf.schema[i].flag & CriUtf.COLUMN_FLAG_UNDEFINED) ):
                raise ValueError("@UTF: unknown column flag combo found")

            # name+default+row isn't possible in CRI's craft tools but rarely found, DEFAULT has priority over ROW [Muramasa Rebirth (Vita)]

            type_size = {
                CriUtf.COLUMN_TYPE_SINT8: 0x01,
                CriUtf.COLUMN_TYPE_UINT8: 0x01,
                CriUtf.COLUMN_TYPE_UINT16: 0x02,
                CriUtf.COLUMN_TYPE_SINT16: 0x02,
                CriUtf.COLUMN_TYPE_UINT32: 0x04,
                CriUtf.COLUMN_TYPE_SINT32: 0x04,
                CriUtf.COLUMN_TYPE_FLOAT:  0x04,
                CriUtf.COLUMN_TYPE_STRING: 0x04,
                CriUtf.COLUMN_TYPE_UINT64: 0x08,
                CriUtf.COLUMN_TYPE_SINT64: 0x08,
               #CriUtf.COLUMN_TYPE_DOUBLE: 0x08,
                CriUtf.COLUMN_TYPE_VLDATA: 0x08,
               #CriUtf.COLUMN_TYPE_UINT128: 0x16
            }
            type = utf.schema[i].type
            value_size = type_size.get(type)
            if value_size is None:
                raise ValueError("@UTF: unknown column type")


            if utf.schema[i].flag & CriUtf.COLUMN_FLAG_NAME:
                utf.schema[i].name = self.get_zstring(utf.string_table, name_offset).decode('utf-8')

            if utf.schema[i].flag & CriUtf.COLUMN_FLAG_DEFAULT:
                utf.schema[i].offset = schema_pos
                schema_pos += value_size
            elif utf.schema[i].flag & CriUtf.COLUMN_FLAG_ROW:
                utf.schema[i].offset = column_offset
                column_offset += value_size

        self.rows = utf.rows
        self.columns = len(utf.schema)
        self.name = utf.table_name

    def get_context(self):
        return self._utf

    def get_column_num(self, column_name):
        utf = self._utf

        # find target column
        for i in range(utf.columns):
            col = utf.schema[i]

            if col.name is None or (col.name != column_name):
                continue
            return i

        return -1

    def get_column_schema(self, num):
        utf = self._utf
        
        if num < 0 or num >= utf.columns:
            return None
        return utf.schema[num]

    def _query(self, row, column):
        utf = self._utf
        result = CriUtf.CriUtfResult()

        if row >= utf.rows or row < 0:
            return None
        if column >= utf.columns or column < 0:
            return None

        col = utf.schema[column]

        result.type = col.type

        if col.flag & CriUtf.COLUMN_FLAG_DEFAULT:
            #if utf.schema_buf:
            #    buf = utf.schema_buf + col.offset
            #else
            data_offset = utf.table_offset + utf.schema_offset + col.offset

        elif col.flag & CriUtf.COLUMN_FLAG_ROW:
            data_offset = utf.table_offset + utf.rows_offset + row * utf.row_width + col.offset

        else:
            # shouldn't happen
            return result # ???

        # read row/constant value (use buf if available)
        if   col.type == CriUtf.COLUMN_TYPE_UINT8:
            result.value = self.get_u8(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_SINT8:
            result.value = self.get_s8(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_UINT16:
            result.value = self.get_u16be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_SINT16:
            result.value = self.get_s16be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_UINT32:
            result.value = self.get_u32be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_SINT32:
            result.value = self.get_s32be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_UINT64:
            result.value = self.get_u64be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_SINT64:
            result.value = self.get_s64be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_FLOAT:
            result.value = self.get_f32be(utf.data, data_offset)
       #elif col.type == CriUtf.COLUMN_TYPE_DOUBLE:
       #    result.value = self.get_d64be(utf.data, data_offset)
        elif col.type == CriUtf.COLUMN_TYPE_STRING:
            name_offset = self.get_u32be(utf.data, data_offset)
            if name_offset > utf.strings_size:
                raise ValueError("Error")
            result.value = self.get_zstring(utf.string_table, name_offset)
        elif col.type == CriUtf.COLUMN_TYPE_VLDATA:
            offset = self.get_u32be(utf.data, data_offset + 0x00)
            size   = self.get_u32be(utf.data, data_offset + 0x04)
            
            offset += utf.table_offset + utf.data_offset

            result.value = (offset, size)
       #elif col.type == CriUtf.COLUMN_TYPE_UINT128:
       #    result.value = utf.data[data_offset : data_offset + 16]
        else:
            return None
        
        return result


    def query(self, row, column_name, type=None):
        column = self.get_column_num(column_name)
        return self.query_pos(row, column, type)

    def query_pos(self, row, col, type=None):
        result = self._query(row, col)

        if not result:
            return None
            
        if type and type != result.type:
            return None
       
        return result.value

    def query_s8(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_SINT8)

    def query_u8(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_UINT8)

    def query_s16(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_SINT16)

    def query_u16(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_UINT16)

    def query_s32(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_SINT32)

    def query_u32(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_UINT32)

    def query_s64(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_SINT64)

    def query_u64(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_UINT64)

    def query_string(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_STRING)

    def query_data(self, row, column_name):
        return self.query(row, column_name, CriUtf.COLUMN_TYPE_VLDATA)
#------------------------------------------------------------------------------

class AwbEntry():
    def __init__(self, filename, hash):
        self.filename = filename
        self.basename = os.path.basename(filename)
        self.hash = hash

class AcbEntry():
    def __init__(self, filename, name, ext, hashes):
        self.filename = filename
        self.basename = os.path.basename(filename)
        self.name = name
        self.ext = ext
        self.hashes = hashes #hash -> awb_name (may be empty = same as name)
    

class CriRenamer():
    EMPTY_HASH = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    def __init__(self):
        self._acbs = [] #AwbEntry
        self._awbs = {} #hash -> AwbEntry

    # helper
    def _get_clean_name(self, filename):
        name = os.path.basename(filename)
        name = os.path.splitext(name)[0]
        return name


    # get AWB name/info from @UTF table
    def _get_awbhashes(self, utf, data):
        offset_size = utf.query_data(0, 'StreamAwbHash')
        if not offset_size:
            return None

        offset, size = offset_size
        if not offset or not size:
            return None

        #print("awb hash: %x %x" % (offset, size))
        buf = data[offset : offset + size]
        hashes = {}

        # direct hash (awbname = acbname)
        if size == 0x10:
            if buf == self.EMPTY_HASH: #all(v == 0 for v in buf)
                # may exist but be all 0s = no external awb (awbname = None)
                return hashes

            hash = buf
            hashes[hash] = ''
            return hashes

        # some files have a subtable with awbnames
        if size != 0x10 and buf[0:4] == b'@UTF':
            utf_awb = CriUtf(buf)
            if utf_awb.name != 'StreamAwb':
                raise ValueError('Unknown table')
            
            # typically 1 but multiple is possible
            for i in range(utf_awb.rows):
                name = utf_awb.query_string(i, 'Name')
                if name:
                    name = name.decode("utf-8") .strip()

                hash_offset, hash_size = utf_awb.query_data(i, 'Hash')
                if hash_size != 0x10:
                    raise ValueError('Unknown AWB hash format')

                hash = buf[hash_offset : hash_offset + hash_size]
                if hash == self.EMPTY_HASH:
                    print("empty AWB hash for " + name)
                    continue

                #print(hash, name)
                hashes[hash] = name

            return hashes

        return hashes

    # get ACB name from @UTF table
    def _get_acbname(self, utf, filename):
        name = utf.query_string(0, 'Name')
        if not name:
            print("warning: name not found in ACB: ", filename)
            name = self._get_clean_name(filename)
            return name

        name = name.decode("utf-8") .strip()
        return name

    def _get_acbext(self, data):
        if data.find(b'ACB Format') > 0:
            return 'acb'
        elif data.find(b'ACF Format') > 0:
            return 'acf'
        else:
            return 'unk'

    def _parse_acb(self, filename, data):
        utf = CriUtf(data)
        if utf.name != 'Header':
            return #not an acb

        name = self._get_acbname(utf, filename)
        ext = self._get_acbext(data)
        hashes = self._get_awbhashes(utf, data)

        entry = AcbEntry(filename, name, ext, hashes)
        self._acbs.append(entry)

    def _parse_awb(self, filename, data):
        hash = hashlib.md5(data).digest()

        entry = AwbEntry(filename, hash)

        # there may be repeats
        if hash not in self._awbs:
            self._awbs[hash] = []
        self._awbs[hash].append(entry)


    # include new file
    def parse_file(self, filename):
        with open(filename, 'rb') as f:
            data = f.read(0x04)

            if data == b'@UTF':
                data += f.read() 
                self._parse_acb(filename, data)
            elif data == b'AFS2':
                data += f.read()
                self._parse_awb(filename, data)
            else:
                return

    # make renames of ACB
    def _make_acb_renames(self, acb):
        renames = []

        ren_name = '%s.%s' % (acb.name, acb.ext)
        if REN_LOWER:
            ren_name = ren_name.lower()

        line = "ren %s %s" % (acb.basename, ren_name)
        if not acb.name or acb.name == '?' or acb.basename.lower() == ren_name.lower():
            line = 'REM #' + line
        renames.append(line)
        
        return renames

    # make renames of AWB based on ACB info
    def _make_awb_renames(self, acb):
        renames = []

        if not acb.hashes:
            return renames

        awb_items = [] #awb_name -> awbs
        for awb_hash, awb_name in acb.hashes.items():
            if not awb_name:
                awb_name = acb.name #common

            awbs = self._awbs.get(awb_hash)
            if not awbs:
                print("no AWB loaded found for hash/name defined in ACB: ", awb_name)
            else:
                for awb in awbs:
                    awb_items.append( (awb_name, awb) )

        seen = set()
        for i, (awb_name, awb) in enumerate(awb_items):

            if awb_name in seen:
                ren_name = '%s[%i].awb' % (awb_name, i)
            else:
                ren_name = '%s.awb' % (awb_name)
            if REN_LOWER:
                ren_name = ren_name.lower()

            line = "ren %s %s" % (awb.basename, ren_name)
            if not awb_name or awb_name == '?' or awb.basename == ren_name:
                line = 'REM #' + line
            renames.append(line)
            seen.add(awb_name)

        return renames

    # save results (at the end after all files are loaded)
    def generate(self):
        renames = []
        
        #for acb_filename, name, awbhashes, ext in self._acbs:
        
        for acb in self._acbs:
            renames += self._make_acb_renames(acb)
            renames += self._make_awb_renames(acb)

        out_name = "_ren_cri.bat"
        with open(out_name, 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
            f.write('\n'.join(renames))

        print(f'wrote {out_name}')


def find_files(dir, pattern, recursive):
    if os.path.isfile(pattern):
        return [pattern]
    if os.path.isdir(pattern):
        dir = pattern
        pattern = None

    for dirsep in '/\\':
        if dirsep in pattern:
            index = pattern.rfind(dirsep)
            if index >= 0:
                dir = pattern[0:index]
                pattern = pattern[index+1:]

    files = []
    for root, dirnames, filenames in os.walk(dir):
        # manually test name as is too, as filter wouldn't handle stuff like "bgm[us].wav"
        for filename in filenames:
            if filename == pattern or fnmatch.fnmatch(filename, pattern):
                files.append(os.path.join(root, filename))

        if not recursive:
            break

    return files

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generates script to rename ACB and AWB hashed names (load all)."
    )

    parser.add_argument("files", nargs="*", help="File names (wildcard work: *.acb audio/**/*.awb)", default=["*"])
    parser.add_argument("-r", "--recursive", action="store_true", help="Enable recursive glob matching (**).")

    args = parser.parse_args()
    return args


def main():
    args = parse_args()
    
    cri = CriRenamer()

    filenames = []
    for pattern in args.files:
        filenames += find_files('.', pattern, args.recursive)

    # pre-process files
    items = []
    for filename in filenames:
        if not os.path.isfile(filename):
            continue
        #print(filename)
        try:
            cri.parse_file(filename)
        except Exception as e:
            raise ValueError(f"Failed parsing '{filename}'") from e

    # generate final file
    cri.generate()

if __name__ == '__main__':
    main()
