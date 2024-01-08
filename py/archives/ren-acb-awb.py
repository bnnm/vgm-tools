# makes a .bat renamer from .acb+awb (put together first)
import glob, struct, os, hashlib

REN_LOWER = False

#TODO with repeats this may happen:
#  00clone.awb
#  blah.acb
#  blah.awb
# generates:
#  REM ren blah.acb blah.acb
#  ren 00clone.awb blah.awb         !!can't rename since blah.awb exists
#  ren blah.awb blah[1].awb         !!but will be renamed here

#--------------------------------------------------------------- 
# from vgmstream's cri_utf.c, mostly migrated as-is from C

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

class CriUtfResult():
    def __init__(self):
        self.type = 0
        self.value = None

class CriUtfColumn():
    def __init__(self):
        self.flag = 0
        self.type = 0
        self.name = ''
        self.offset = 0

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


class CriUtf():
    def __init__(self, data, table_offset=0):
        self.rows = 0
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
        utf = CriUtfContext()
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
        if utf.schema_size >= UTF_MAX_SCHEMA_SIZE:
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

        utf.table_name = self.get_zstring(utf.string_table, utf.name_offset)

        utf.schema = [None] * utf.columns

        for i in range (utf.columns):
            utf.schema[i] = CriUtfContext()
        
            info = self.get_u8(utf.schema_buf, schema_pos + 0x00)
            name_offset = self.get_u32be(utf.schema_buf, schema_pos + 0x01)

            if name_offset > utf.strings_size:
                raise ValueError("Error")
            schema_pos += 0x01 + 0x04

            utf.schema[i].flag = info & COLUMN_BITMASK_FLAG
            utf.schema[i].type = info & COLUMN_BITMASK_TYPE
            utf.schema[i].name = None
            utf.schema[i].offset = 0

            # known flags are name+default or name+row, but name+default+row is mentioned in VGMToolbox
            # even though isn't possible in CRI's craft utils (meaningless), and no name is apparently possible
            if  (utf.schema[i].flag == 0 or
                not (utf.schema[i].flag & COLUMN_FLAG_NAME) or
                ((utf.schema[i].flag & COLUMN_FLAG_DEFAULT) and (utf.schema[i].flag & COLUMN_FLAG_ROW)) or
                 (utf.schema[i].flag & COLUMN_FLAG_UNDEFINED) ):
                raise ValueError("@UTF: unknown column flag combo found")


            type_size = {
                COLUMN_TYPE_UINT8: 0x01,
                COLUMN_TYPE_SINT8: 0x01,
                COLUMN_TYPE_UINT16: 0x02,
                COLUMN_TYPE_SINT16: 0x02,
                COLUMN_TYPE_UINT32: 0x04,
                COLUMN_TYPE_SINT32: 0x04,
                COLUMN_TYPE_FLOAT:  0x04,
                COLUMN_TYPE_STRING: 0x04,
                COLUMN_TYPE_UINT64: 0x08,
                COLUMN_TYPE_SINT64: 0x08,
               #COLUMN_TYPE_DOUBLE: 0x08,
                COLUMN_TYPE_VLDATA: 0x08,
               #COLUMN_TYPE_UINT128: 0x16
            }
            type = utf.schema[i].type
            value_size = type_size.get(type)
            if value_size is None:
                raise ValueError("@UTF: unknown column type")


            if utf.schema[i].flag & COLUMN_FLAG_NAME:
                utf.schema[i].name = self.get_zstring(utf.string_table, name_offset)

            if utf.schema[i].flag & COLUMN_FLAG_DEFAULT:
                utf.schema[i].offset = schema_pos
                schema_pos += value_size


            if utf.schema[i].flag & COLUMN_FLAG_ROW:
                utf.schema[i].offset = column_offset
                column_offset += value_size

        self.rows = utf.rows
        self.name = utf.table_name


    def get_column(self, column_name):
        utf = self._utf

        # find target column
        for i in range (utf.columns):
            col = utf.schema[i]

            if col.name is None or (col.name != column_name):
                continue
            return i

        return -1

    def _query(self, row, column):
        utf = self._utf
        result = CriUtfResult()
    
        if row >= utf.rows or row < 0:
            return None
        if column >= utf.columns or column < 0:
            return None

        col = utf.schema[column]

        result.type = col.type

        if col.flag & COLUMN_FLAG_DEFAULT:
            #if utf.schema_buf:
            #    buf = utf.schema_buf + col.offset
            #else
            data_offset = utf.table_offset + utf.schema_offset + col.offset

        elif col.flag & COLUMN_FLAG_ROW:
            data_offset = utf.table_offset + utf.rows_offset + row * utf.row_width + col.offset

        else:
            # shouldn't happen
            return result # ???

        # read row/constant value (use buf if available)
        if   col.type == COLUMN_TYPE_UINT8:
            result.value = self.get_u8(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_SINT8:
            result.value = self.get_s8(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_UINT16:
            result.value = self.get_u16be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_SINT16:
            result.value = self.get_s16be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_UINT32:
            result.value = self.get_u32be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_SINT32:
            result.value = self.get_s32be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_UINT64:
            result.value = self.get_u64be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_SINT64:
            result.value = self.get_s64be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_FLOAT:
            result.value = self.get_f32be(utf.data, data_offset)
       #elif col.type == COLUMN_TYPE_DOUBLE:
       #    result.value = self.get_d64be(utf.data, data_offset)
        elif col.type == COLUMN_TYPE_STRING:
            name_offset = self.get_u32be(utf.data, data_offset)
            if name_offset > utf.strings_size:
                raise ValueError("Error")
            result.value = self.get_zstring(utf.string_table, name_offset)
        elif col.type == COLUMN_TYPE_VLDATA:
            offset = self.get_u32be(utf.data, data_offset + 0x00)
            size   = self.get_u32be(utf.data, data_offset + 0x04)
            
            offset += utf.table_offset + utf.data_offset

            result.value = (offset, size)
       #elif col.type == COLUMN_TYPE_UINT128:
       #    result.value = utf.data[data_offset : data_offset + 16]
        else:
            return None
        
        return result


    def query(self, row, column_name, type=None):
        column = self.get_column(column_name)
        result = self._query(row, column)

        if not result:
            return None
            
        if type and type != result.type:
            return None
       
        return result.value

    def query_s8(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_SINT8)

    def query_u8(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_UINT8)

    def query_s16(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_SINT16)

    def query_u16(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_UINT16)

    def query_s32(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_SINT32)

    def query_u32(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_UINT32)

    def query_s64(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_SINT64)

    def query_u64(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_UINT64)

    def query_string(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_STRING)

    def query_data(self, row, column_name):
        return self.query(row, column_name, COLUMN_TYPE_VLDATA)
    
# -------------------------------------------------------------------------------

class CriRenamer():
    def __init__(self):
        self._acbs = [] #(filename, acbname, awbhash)
        self._awbs = {} #hash to filename



    def _get_awbhash(self, filename, data, utf):
        find_target = b'StreamAwb\0Name\0Hash\0'

        offset_size = utf.query_data(0, b'StreamAwbHash')
        if not offset_size:
            return None

        offset, size = offset_size
        if not offset or not size:
            return None
        buf = data[offset:offset+size]

        # direct hash (awbname = acbname)
        if size == 0x10:
            hash = buf
            return hash

        # may exist but be all 0s = no external awb (awbname = None)
        if size == 0x10 and all(v == 0 for v in buf):
            return None

        # some files have a subtable with awbname
        if size != 0x10 and buf[0:4] == b'@UTF':
            utfawb = CriUtf(buf)
            if utfawb.name != b'StreamAwb':
                raise ValueError('Unknown table')
            if utfawb.rows != 1:
                raise ValueError('Unknown streamawb info')

            awbname = utfawb.query_string(0, b'Name')
            offset, size = utfawb.query_data(0, b'Hash')
            if size != 0x10:
                raise ValueError('Unknown table')
            hash = buf[offset:offset+size]
            return hash

        return None

    def _get_acbname(self, filename, data, utf):
        name = utf.query_string(0, b'Name')
        if not name:
            print("warning: name not found in:", filename)
            #return '?'
            return os.path.splitext(filename)[0]

        name = name.decode("utf-8") .strip()
        return name

    def _get_awbhash_old(self, filename, data):
        find_target = b'StreamAwb\0Name\0Hash\0'

        pos = data.find(find_target)
        if pos < 0:
            return None
        pos += len(find_target)

        end = data.find(b'\x00', pos)
        if end < 0:
            return None
        end += 1
        return data[end:end+0x10]
    
    def _get_acbname_old(self, filename, data):
        find_target = b'Build:\n\0'

        pos = data.find(find_target)
        if pos < 0:
            print("warning: name not found in:", filename)
            return '?'
        pos += len(find_target)

        end = data.find(b'\x00', pos)
        if end < 0:
            print("warning: wrong end in:", filename)
            return '?'

        name = data[pos:end]
        if not name or name == b'\x00':
            print("warning: empty name in:", filename)
            return ''

        name = name.decode("utf-8") .strip()
        return name
    
    def _parse_acb(self, filename, data):
        utf = CriUtf(data)
        if utf.name != b'Header':
            return #not an acb

        acbname = self._get_acbname(filename, data, utf)
        #acbname = self._get_acbname_old(filename, data)
        # could also find awb name but almost always it's the same as awb (in rare cases could be N awbs)
        awbhash = self._get_awbhash(filename, data, utf)
        #awbhash = self._get_awbhash_old(filename, data)
        
        if data.find(b'ACB Format') > 0:
            ext = 'acb'
        elif data.find(b'ACF Format') > 0:
            ext = 'acf'
        else:
            ext = 'unk'
        
        elem = (filename, acbname, awbhash, ext)
        self._acbs.append(elem)
        pass

    def _parse_awb(self, filename, data):
        hash = hashlib.md5(data).digest()

        # there may be repeats
        if hash not in self._awbs:
            self._awbs[hash] = []
        self._awbs[hash].append(filename)
        pass

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

    # save results (at the end after all files are loaded)
    def generate(self):
        renames = []
        for acb_filename, name, awbhash, ext in self._acbs:

            if True:
                acb_basename = os.path.basename(acb_filename)

                ren_name = '%s.%s' % (name, ext)
                if REN_LOWER:
                    ren_name = ren_name.lower()
                line = "ren %s %s" % (acb_basename, ren_name)
                if not name or name == '?' or acb_basename.lower() == ren_name.lower():
                    line = 'REM #' + line
                renames.append(line)

            awb_filenames = self._awbs.get(awbhash)
            if awb_filenames:
                for i, awb_filename in enumerate(awb_filenames):
                    awb_basename = os.path.basename(awb_filename)
                    
                    if i > 0:
                        ren_name = '%s[%i].awb' % (name, i)
                    else:
                        ren_name = '%s.awb' % (name)
                    
                    if REN_LOWER:
                        ren_name = ren_name.lower()
                    line = "ren %s %s" % (awb_basename, ren_name)
                    if not name or name == '?' or awb_basename == ren_name:
                        line = 'REM #' + line
                    renames.append(line)

        with open("_ren_cri.bat", 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
            f.write('\n'.join(renames))


def main():
    cri = CriRenamer()

    filenames = glob.glob("*")
    
    items = []
    for filename in filenames:
        if not os.path.isfile(filename):
            continue
        #print(filename)
        cri.parse_file(filename)

    cri.generate()
main()


def testacb():
    with open('000.acb', 'rb') as f:
        data = f.read()
    utf = CriUtf(data, 0)
    print(utf.rows, utf.name)
    print( utf.query_string(0, b'Name') )
    print("%x %x" % utf.query_data(0, b'StreamAwbHash') )
    print("%x %x" %  utf.query_data(0, b'AwbFile') )
#test()
