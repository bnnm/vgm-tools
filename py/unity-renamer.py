# renames unity .bytes and joins chunked files
import glob, os, re


files = glob.glob('**/*.bytes', recursive=True)
files.sort()

re_end = re.compile('.+-[0-9][0-9][0-9]')

for file in files:
    #base = os.path.basename(file)
    base1, _ = os.path.splitext(file)
    
    # removes bytes
    os.rename(file, base1)
