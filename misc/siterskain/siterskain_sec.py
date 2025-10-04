# SITER SKAIN .sec decryptor by bnnm [RefleX (PC), ALLTYNEX Second (PC)]
#
# Run in the same folder to decrypt all .sec, or drag-and-drop files.


import sys, os, glob

# reversed from the ALLTYNEX Second trial (alltynex2nd.exe), see CXor refs (0x005870B0)
class UnxorContext:
    def __init__(self):
        self.unk = 0
        self.key = bytearray(16)
        self.key_len = 0
        self.key_pos = 0
        self.scramble = 0

# 0x53BA900
def xor_setup_key(ctx: UnxorContext, key: bytes):
    if key and len(key) > 0:
        max_len = min(len(key), 15)
        ctx.key[:max_len] = key[:max_len]
        ctx.key[max_len] = 0
        ctx.key_len = max_len
        ctx.scramble = 0
        ctx.key_pos = 0
    else:
        ctx.key_len = 0
        ctx.scramble = 0
        ctx.key_pos = 0

def ror1(byte: int, shift: int) -> int:
    shift %= 8
    return ((byte >> shift) | (byte << (8 - shift))) & 0xFF

# 0x53BA50
def xor_undo_byte(ctx: UnxorContext, byte: int) -> int:
    if ctx.key_len == 0:
        return byte
    key = ctx.key[ctx.key_pos]
    if key != 0:
        ctx.key_pos += 1
    else:
        key = ctx.scramble & 0xFF
        ctx.scramble += 1
        ctx.key_pos = 0
    shift = (key + (ctx.scramble & 0xFF)) & 7
    #print(f"{key:02x} ^ ror1({byte:02x}, {shift}) = {key:02x} ^ {ror1(byte, shift):02x} = {key ^ ror1(byte, shift):02x}")
    return key ^ ror1(byte, shift)

# 0x53BB10
def xor_process(ctx: UnxorContext, src: bytes, key: bytes) -> bytes:
    xor_setup_key(ctx, key)
    dst = bytearray(len(src))
    for i in range(len(src)):
        dst[i] = xor_undo_byte(ctx, src[i])
    return bytes(dst)

def get_output_filename(base: str, decoded: bytes) -> str:
    if decoded.startswith(b'RIFF'):
        return base + '.wav'
    elif decoded.startswith(b'OggS'):
        return base + '.ogg'
    else:
        return base + '.dec'

def process_file(filename: str):
    try:
        with open(filename, 'rb') as f:
            data = f.read()

        key = data[0x00:0x10]
        skip_bytes = 0x20
        ctx = UnxorContext()
        decoded = xor_process(ctx, data[skip_bytes:], key)

        base, _ = os.path.splitext(filename)
        out_filename = get_output_filename(base, decoded)

        with open(out_filename, 'wb') as f:
            f.write(decoded)
    except Exception as e:
        print(f"Error processing {filename}: {e}")

def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else glob.glob("*.sec")
    if not files:
        sys.exit("No input files found.")

    print("Processing...")

    for file in files:
        process_file(file)

if __name__ == "__main__":
    main()
