# dumb XORer for quick tests

#!/usr/bin/env python3

import os
import sys
import glob
import argparse
import re


def parse():
    description = (
        "decrypts xor'ed files with keyvalue or keyfile (defaults to key.bin)"
    )
    epilog = (
        "examples:\n"
        "  %(prog)s *.ogg\n"
        "  %(prog)s **/bgm???.* -f xorkey.bin\n"
        "  %(prog)s bgm_??.* -k aabb\n"
    )

    parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("files", help="files to get (wildcards work)")
    parser.add_argument("-f","--keyfile", help="key in file", default="key.bin")
    parser.add_argument("-k","--keyvalue", help="key in hex")
    parser.add_argument("-s","--start", help="start offset")
    return parser.parse_args()


def is_file_ok(args, glob_file):
    if not os.path.isfile(glob_file):
        return False

    if args.keyfile == glob_file:
        return False

    if glob_file.endswith(".py"):
        return False
    return True


def decrypt(data, key, pos):
    data_len = len(data)
    key_len = len(key)
    for i in range(0,data_len):
        data[i] ^= key[(pos+i) % key_len]
    return data


def main(): 
    args = parse()

    # get target files
    glob_files = glob.glob(args.files)

    if args.keyvalue:
        key = bytearray.fromhex(args.keyvalue)
        #key = bytes.fromhex(args.keyvalue)  #python3
    else:
        with open(args.keyfile, 'rb') as infile:
            key = bytearray(infile.read())

    # process matches and add to output list
    chunk_size = 0x4000
    files = []
    for glob_file in glob_files:
        if not is_file_ok(args, glob_file):
            continue
        print("decrypting " + glob_file + "...")

        with open(glob_file, 'rb') as infile, open(glob_file + ".dec", 'wb') as outfile:
            start = 0
            if args.start:
                start = int(args.start, 0)
                data = infile.read(start)
                outfile.write(data)

            infile.seek(start)
            size = os.path.getsize(glob_file)
            for i in range(0, size, chunk_size):
                data = bytearray(infile.read(chunk_size))
                data_dec = decrypt(data, key, i)
                outfile.write(data_dec)

if __name__ == "__main__":
    main()
