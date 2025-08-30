# unpacks .wem/bnk from raw/binary MonoBehaviours
#
# - use some unity asset extractor clone to load assets (mainly in some "streamed" folder)
#   - if files are not recognized may need to set some version, like "2022.3.51f1" 
#     (check base assets with hex editor, some may have the actual version)
# - go to options and set 'extract as source file name', as some files may be overwritten otherwise
# - use export menu > raw assets > export selected (or 'all') to some base folder
# - put this .py to in that folder and run it
# - should create SFX + language folders with .wem and .bnk
# - use wwiser

import os
import struct
import glob

BASEDIR = '.'

def read_le_int(f, num_bytes):
    return int.from_bytes(f.read(num_bytes), byteorder='little')

def read_string(f, size):
    return f.read(size).decode('utf-8')

def skip_padding(f):
    pos = f.tell()
    pad = (4 - pos % 4) % 4
    f.seek(pad, os.SEEK_CUR)

def process_dat_file(dat_file_path):
    with open(dat_file_path, 'rb') as f:
        val1 = read_le_int(f, 4)
        val2 = read_le_int(f, 4)
        val3 = read_le_int(f, 4)
        val4 = read_le_int(f, 4)
        val5 = read_le_int(f, 4)

        hash_bytes = f.read(0x08)

        ext = None
        if hash_bytes == b'\x5E\x7C\x17\xDB\xD1\x69\xFF\x1F':
            ext = 'wem'
        if hash_bytes == b'\x1E\x89\xBC\xD1\x96\x6D\xD2\x85':
            ext = 'bnk'
        if not ext:
            return
        print(dat_file_path)

        assert val1 == 0
        assert val2 == 0
        assert val3 == 0
        assert val4 == 1
        assert val5 in (0, 1)

        name_size = read_le_int(f, 4)
        file_name = read_string(f, name_size)
        skip_padding(f)

        file_size = read_le_int(f, 4)
        file_data = f.read(file_size)
        skip_padding(f)

        assert read_le_int(f, 4) == 0x10
        hash_bytes = f.read(0x10)

        pack_size = read_le_int(f, 4)
        pack_name = read_string(f, pack_size)
        skip_padding(f)

        # read names list
        names_list = []
        if ext == 'bnk':
            count = read_le_int(f, 4)
            for _ in range(count):
                name_size = read_le_int(f, 4)
                name = read_string(f, name_size)
                names_list.append(name)
                skip_padding(f)

        os.makedirs(pack_name, exist_ok=True)
        output_filename = f"{pack_name}/{file_name}.{ext}"
        with open(output_filename, 'wb') as output_file:
            output_file.write(file_data)

        # Write the list of names into a text file
        if names_list:
            names_text = "\n".join(names_list)
            with open(f"_names.txt", 'a') as names_file:
                names_file.write(names_text)
                names_file.write('\n')

def process_all_dat_files():
    #files = os.listdir(BASEDIR)
    files = glob.glob('**/*.dat', recursive = True)
    
    for filename in files:
        if filename.endswith('.dat'):
            #dat_file_path = os.path.join(directory, filename)
            process_dat_file(filename)

if __name__ == '__main__':
    process_all_dat_files()
