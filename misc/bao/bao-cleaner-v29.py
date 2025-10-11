# Moves unusable *.bao to a subfolder
# Only for v29+ .bao (Splinter Cell Conviction).
import os, struct, shutil, glob

MOVE_MEMORY_STREAM_BAOS = False

def get_u32(f, big_endian):
    if big_endian:
        return struct.unpack('>I', f.read(4))[0]
    else:
        return struct.unpack('<I', f.read(4))[0]

def get_u32be(f):
    return struct.unpack('>I', f.read(4))[0]

def is_usable(f):
    bao_id = get_u32be(f)

    if bao_id & 0x00FF0000 < 0x00290000:
        print("unknown version")
        return external_ids


    big_endian = False
    f.seek(0x14)
    bao_class = get_u32(f, big_endian)
    if bao_class < 0x1000:
        big_endian = True
        f.seek(0x14)
        bao_class = get_u32(f, big_endian)

    if bao_class in [0x30000000, 0x50000000]:
        if MOVE_MEMORY_STREAM_BAOS:
            return False
        return True

    if bao_class != 0x20000000:
        return False

    f.seek(0x1c + 0x2c)
    header_type = get_u32(f, big_endian)

    if header_type not in [0x01, 0x05, 0x06]:
        return False

    return True

def find_rejected_files():
    rejected = set()
    
    files = glob.glob('**/*.bao', recursive=True) #header baos
    for filepath in files:
        try:
            with open(filepath, 'rb') as f:
                if not is_usable(f):
                    rejected.add(filepath)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
    return rejected

def move_unused_files(unused_list):
    if not unused_list:
        return

    unused_dir = os.path.join('.', 'unused')
    os.makedirs(unused_dir, exist_ok=True)

    for filename in unused_list:
        src = filename
        dst = os.path.join(unused_dir, filename)
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)

def move_unreferenced_files():
    rejected = find_rejected_files()
    move_unused_files(rejected)

if __name__ == "__main__":
    move_unreferenced_files()
