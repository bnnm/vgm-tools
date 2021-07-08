# finds finary text/stuff in files and moves them to subdir
import os
import sys
import struct

movedir = "_moved"
texts = [b'ogg', b'OGG', b'Ogg', b'bgm', b'BGM', b'Bgm', b'sound', b'SOUND', b'Sound', b'audio', b'AUDIO', b'Audio']

def move_file(filename, dir):
    if not os.path.exists(dir):
        os.makedirs(dir)
    os.rename(filename, dir + "/" + filename)
    return

# main
for filename in os.listdir("."):
    if not os.path.isfile(filename):
        continue
    if filename.endswith('.py'):
        continue

    #print("file %s" % filename)
    in_file = open(filename, "rb")
    data = in_file.read()
    in_file.close()
    
    move = False
    for text in texts:
        if text in data:
            move = True

    if not move:
        continue

    dir = "%s" % (movedir)
    move_file(filename, dir)

#wait = input("done")
