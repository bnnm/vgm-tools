# GOOGLE'S PROTOCOL BUFFERS SIMPLE PRINTER (https://protobuf.dev)
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
    for i in range(len(data)):
        if data[i] < 0x09:
            return False
            
    return True
   

def parse_obj(data, level):
    pos = 0
    while pos < len(data):
        last_pos = pos

        field_number, wire_type, size = parse_tlv(data, pos)
        pos += size

        #print("* %s%x: %s [%s]-%x" % (' '*level*2, field_number, data[0:0x10], wire_type, pos) )

        parser = TYPE_PARSERS[wire_type]
        value, size = parser(data, pos)
        pos += size

        info_type = _TYPES.get(wire_type)
        
        # may be a string, bytes, or messages
        # TODO better detection
        if wire_type == 2:
            if is_string(value):
                value = value.decode("utf-8") 
                print("%s%x: %s [%s]-0x%x" % (' '*level*2, field_number, value, info_type, last_pos) )
            else:
                print("%s%x: %s [%s]-0x%x" % (' '*level*2, field_number, '(message)', info_type, last_pos) )
                size = parse_obj(value, level+1)
                pos += size
        else:
            print("%s%x: %s [%s]-0x%x" % (' '*level*2, field_number, value, info_type, last_pos) )


    return pos

##
# https://protobuf.dev/programming-guides/encoding/
# https://www.freecodecamp.org/news/googles-protocol-buffers-in-python/

#with open('msg.bin', 'wb') as f:
#    f.write(b'\x08\xd2\t\x12\x03Tim\x1a(\x08\x04\x12\x18Test ProtoBuf for Python\x1a\n31.10.2019')

with open('catalog_decompressed.bin', 'rb') as f:
    data = f.read()
parse_obj(data, 0)

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
