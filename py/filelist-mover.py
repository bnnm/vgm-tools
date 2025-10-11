# moves files in a txt list to another folder
import os
import shutil

file_list_path = '_files.txt'
destination_dir = 'files'
os.makedirs(destination_dir, exist_ok=True)

with open(file_list_path, 'r') as f:
    paths = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

for path in paths:
    if not os.path.isfile(path):
        continue
    dst = os.path.join(destination_dir, path)
    dst_dir = os.path.dirname(dst)
    os.makedirs(dst_dir, exist_ok=True)
    shutil.move(path, dst)
