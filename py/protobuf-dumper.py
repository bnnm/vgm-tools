# GOOGLE'S PROTOCOL BUFFERS SIMPLE PRINTER (https://protobuf.dev)
# https://protobuf.dev/programming-guides/encoding/
# https://www.freecodecamp.org/news/googles-protocol-buffers-in-python/
#
# Protocol buffers are a generic serialized object format:
# - define objects in google's text format
# - compile objects and use in application
# - write objects to binary (using the compiled definition)
#   - binary only has data and number references to compiled object fields,
#     so you don't know how field's names without the object definition
# - read objects from binary to compiled objects definitions
# Objects can be printed partially in simple cases, but needs a complete definition
# for more complex fields. Should be ok enough for json-like key:val.
import sys, os

DEBUG = False
_TYPES = {
    0: 'VARINT',
    1: 'I64',
    2: 'LEN',
    3: 'SGROUP',
    4: 'EGROUP',
    5: 'I32',
}

def parse_empty(data, pos):
    return (0, 0)

# - int32, int64, uint32, uint64, sint32, sint64, bool, enum
# numbers are encoded as 7 bit; when MSB is set number continues to next, until no MSB is set
# "9601" > 96 is 16 w/ msb (continues next 7b): 16 | (01<<7) = 0x0196 = 150
def parse_varint(data, pos):
    total = 0
    shift = 0
    value = 0
    while True:
        msb = data[pos] & 0x80
        val = data[pos] & 0x7F
        val = val << shift
        
        # todo signeds
        value = value | val

        shift += 7
        total += 1
        pos += 1

        if not msb:
            break
    return (value, total)

# - string, bytes, embedded messages, packed repeated fields
def parse_len(data, pos):
    total = 0
    # get payload size
    value, size = parse_varint(data, pos)
    pos += size
    total += size

    data = data[pos: pos+value]
    total += value

    return (data, total)

# - i32
def parse_i32(data, pos):
    total = 0
    # get payload size
    size = 4
    value = data[0] << 0 | data[1] << 8  | data[2] << 16  | data[3] << 24
    pos += size
    total += size

    return (value, total)


def parse_tlv(data, pos):
    total = 0
    val, size = parse_varint(data, pos)
    pos += size
    total += size
    
    #val = data[pos]

    # read TLV
    #msb = val & 0x80
    #if msb:
    #    raise ValueError("unexpected MSB")
    field_number = val >> 3 # upper N bits
    wire_type = val & 0x07 #lower 3 bits
    return (field_number, wire_type, total)

TYPE_PARSERS = {
    0: parse_varint,
    2: parse_len,
    #3: parse_empty,
    #4: parse_empty,
    5: parse_i32,
}
def is_string(data):
    utf_count = 0
    utf_start = None
    for i in range(len(data)):
        if data[i] < 0x09:
            return False
        if data[i] >= 0x80:
            utf_count += 1
            if utf_start is None:
                utf_start = i
            
    if utf_count > 0:
        if utf_start < 3: #early bytes = protocol buf info
            return false
        try:
            data.decode("utf-8") 
        except:
            return False

    return True
   

def parse_obj(data, level, lines):
    pos = 0
    while pos < len(data):
        last_pos = pos

        field_number, wire_type, size1 = parse_tlv(data, pos)
        pos += size1

        parser = TYPE_PARSERS.get(wire_type, None)
        if not parser:
            raise ValueError("parser not implemented: " + str(wire_type) + " - " + str(data[last_pos:last_pos+0x10]))
        
        info_type = _TYPES.get(wire_type)
        value, size2 = parser(data, pos)
        pos += size2

        #if DEBUG:
        #    print("* %sfld=%x: val=%s [%s]" % (' '*level*2, field_number, value, info_type) )

        # may be a string, bytes, or messages
        if wire_type == 2:
            if is_string(value):
                text = value.decode("utf-8") 
                line = '%s%x: %s' % (' '*level*2, field_number, text)
                lines.append(line)
                if DEBUG:
                    print("%s [%s:%x]-0x%x" % (line, info_type, size1+size2, last_pos) )
            else:
                text = '(message)'
                line = '%s%x: %s' % (' '*level*2, field_number, text)
                lines.append(line)
                if DEBUG:
                    print("%s [%s:%x]-0x%x" % (line, info_type, size1+size2, last_pos) )

                size = parse_obj(value, level+1, lines)
                #pos += size
        else:
            if isinstance(text, (bytes, bytearray)):
                text = '(object)'
            else:
                text = value
            line = '%s%x: %s' % (' '*level*2, field_number, text)
            lines.append(line)
            if DEBUG:
                print("%s [%s:%x]-0x%x" % (line, info_type, size1+size2, last_pos) )

    return pos

def main():
    if len(sys.argv) <= 1:
        print("Usage: %s infile" % (os.path.basename(sys.argv[0])))
        return
    for infile in sys.argv[1:]:
        if True:
        #try:
            lines = []
            with open(infile, 'rb') as f:
                data = f.read()
            parse_obj(data, 0, lines)
            with open(infile + '.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
        #except Exception  as e:
        #    print("couldn't parse: " + str(e))

main()

#class MessageObject:
#    def __init__(self):
#        self.fields = []
#        self.enums = []
#        self.objects = []
#
#class MessageField:
#    def __init__(self):
#        self.number = 0
#        self.type = ''
#        self.name = ''
#        self.required = False
#        self.optional = False
#        self.repeated = False
#
#class MessageEnum:
#    def __init__(self):
#        self.values = {}
