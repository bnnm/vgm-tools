# importable CRI @UTF parser
# 
# @UTF is a simple database-like table of columns and rows,
# with row data encoded in various types (u32, string, blobs, etc).
#
# example:
#   import sys
#   sys.dont_write_bytecode = True
#
#   from criutf import *  # (or simply copy-paste code below)
#   ...
#   data = f.read()
#   utf = CriUtf(data)
#   for i in range (utf.rows):
#       value = utf.query(i, "column_name")
#       print(f"{utf.name}[{i}]: {value}")

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

        for i in range (utf.columns):
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
