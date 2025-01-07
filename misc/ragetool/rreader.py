import struct

class Reader():
    def __init__(self, file, data):
        self.file = file
        self._data = data

        self._pos = 0
        self._is_be = False

    def chunk(self, size):
        chunk = self._data[self._pos : self._pos + size];
        self._pos += size
        return chunk

    def fourcc(self):
        return self.chunk(4)

    def _unpack(self, fmt, size):
        
        if fmt[0:1] not in ('<','>'):
            if self._is_be:
                endian = '>'
            else:
                endian = '<'
            fmt = endian + fmt
        val, = struct.unpack_from(fmt, self._data, self._pos)
        self._pos += size
        return val

    def f32(self):
        return self._unpack('f', 4)

    def u64(self):
        return self._unpack('Q', 8)

    def s64(self):
        return self._unpack('q', 8)

    def u32(self):
        return self._unpack('I', 4)

    def u32be(self):
        return self._unpack('>I', 4)

    def s32(self):
        return self._unpack('i', 4)

    def u16(self):
        return self._unpack('H', 2)

    def s16(self):
        return self._unpack('h', 2)

    def u8(self):
        return self._unpack('B', 1)

    def pos(self, val=None):
        if val is not None:
            self._pos = val
        return self._pos

    def seek(self, val=None):
        self.pos(val)
    
    def tell(self):
        return self.pos()
    
    def set_be(self, value):
        self._is_be = value
