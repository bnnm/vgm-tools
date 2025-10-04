# Moves unused 3*.bao/5*.bao files so a subfolder
# Use after removing 2*.bao (header)
# Only for .bao from Beowulf.

import os, struct, shutil, glob

def get_u32(f, big_endian):
    if big_endian:
        return struct.unpack('>I', f.read(4))[0]
    else:
        return struct.unpack('<I', f.read(4))[0]

def get_u32be(f):
    return struct.unpack('>I', f.read(4))[0]

def find_companion_baos(folder):
    files = []
    files += glob.glob(os.path.join(folder, '3*.bao')) #memory baos
    files += glob.glob(os.path.join(folder, '5*.bao')) #stream baos
    return [os.path.basename(f).lower() for f in files]

def find_cue_baos(folder):
    files = glob.glob(os.path.join(folder, '1*.bao')) #cue baos
    return [os.path.basename(f) for f in files]


def add_id(external_ids, ext_id):
    external_ids.add(f"{ext_id:08x}.bao")
    if ext_id & 0x50000000:
        memory_id = (ext_id & 0x0FFFFFFF) | 0x30000000 #implicit in some cases
        external_ids.add(f"{memory_id:08x}.bao")

def extract_external_ids(f):
    external_ids = set()
    bao_id = get_u32be(f)

    if bao_id & 0x00FF0000 != 0x001B0000:
        print("unknown version")
        return external_ids

    bao_skip = get_u32(f, True)
    if bao_skip >= 0x100:
        f.seek(0x04)
        bao_skip = get_u32(f, False)

    big_endian = True

    f.seek(bao_skip + 0x04)
    bao_type = get_u32(f, big_endian)
    if bao_type > 0x100:
        big_endian = False
        f.seek(bao_skip + 0x08)
        bao_type = get_u32(f, big_endian)


    if bao_type == 0x01: #audio
        f.seek(bao_skip + 0x1c)
        ext_id = get_u32(f, big_endian)
        add_id(external_ids, ext_id)

    elif bao_type == 0x05: #sequence
        f.seek(bao_skip + 0x2c)
        count = get_u32(f, big_endian)

        f.seek(bao_skip + 0x7c)
        for _ in range(count):
            ext_id = get_u32(f, big_endian)
            add_id(external_ids, ext_id)
            f.seek(0x10, 1)

    elif bao_type == 0x06: #layer
        f.seek(bao_skip + 0x4c)
        ext_id = get_u32(f, big_endian)
        add_id(external_ids, ext_id)

    else:
        return None

    return external_ids

def get_external_ids(folder):
    files = glob.glob(os.path.join(folder, '2*.bao')) #header baos
    external_ids = set()
    rejected = set()
    for filepath in files:
        try:
            with open(filepath, 'rb') as f:
                items = extract_external_ids(f)
                if items is None:
                    rejected.add(os.path.basename(filepath))
                    continue
                    
                external_ids.update(items)
        except Exception as e:
            print(f"Error reading {os.path.basename(filepath)}: {e}")
    return external_ids, rejected

def move_unused_files(folder, unused_list):
    if not unused_list:
        return

    unused_dir = os.path.join(folder, 'unused')
    os.makedirs(unused_dir, exist_ok=True)

    for filename in unused_list:
        src = os.path.join(folder, filename)
        dst = os.path.join(unused_dir, filename)
        if os.path.exists(src):
            shutil.move(src, dst)

def move_unreferenced_files(folder):
    baos = find_companion_baos(folder)
    external_ids, rejected = get_external_ids(folder)

    unused = [f for f in baos if f not in external_ids]
    unused += find_cue_baos(folder)
    unused += rejected
    move_unused_files(folder, unused)

if __name__ == "__main__":
    move_unreferenced_files('.')
