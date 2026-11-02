import os, struct, glob

def extract_cache_ids():
    output_lines = []
    files = glob.glob("**/*.wem", recursive=True)
    for path in files:
        #basename = os.path.basename(path)
        
        try:
            with open(path, 'rb') as f:
                header = f.read(0x200)
                index = header.find(b'hash')
                if index == -1:
                    print(f"{path}: 'hash' not found in first 0x200 bytes")
                    continue

                f.seek(index + 4)
                value = struct.unpack('<I', f.read(4))[0]
                if value != 0x10:
                    print(f"{path}: 'hash' found but value after is not 0x10 (found 0x{value:08x})")
                    continue

                cache_id = struct.unpack('<I', f.read(4))[0]
                cache_hex = f"0x{cache_id:08x}"
                output_lines.append(f"{path}: {cache_hex}")

        except Exception as e:
            print(f"Error processing {path}: {e}")

    with open('filename-cacheid.txt', 'w') as out_file:
        for line in output_lines:
            out_file.write(line + '\n')

if __name__ == "__main__":
    extract_cache_ids()
