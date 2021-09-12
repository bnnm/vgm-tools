# G1LExtract
#
# Original version by soneek
# v20180320 by bnnm 
#   (extract unique entries only, fix KOVS/ATSL, etc)
# v20210912 by bnnm 
#   (python3, subdirs)

import sys
import os
import struct

def readu32(file, le=True):
    if le:
        return struct.unpack("<I", file.read(4))[0]
    else:
        return struct.unpack(">I", file.read(4))[0] 

subfolders = True
if len(sys.argv) != 2:
   print("Usage: G1LExtract infile.g1l")
   exit()

g1l = open(sys.argv[1], 'rb')
fourcc = g1l.read(4)
if fourcc == b"_L1G":
    le = True
elif fourcc == b"G1L_":
    le = False
else:
    print("Infile is not a G1L file")
    exit()

g1l.seek(8)
ext = ".g1l"

fullSize = readu32(g1l, le)
headerSize = readu32(g1l, le)
codec = readu32(g1l, le)
fileCount = readu32(g1l, le)

offsetsDone = {}
filesDone = 0;

for i in range(fileCount):
    g1l.seek(0x18+i*4)
    #print(hex(g1l.tell()))
    fileOffset = readu32(g1l, le)
    
    # entries can point to the same file multiple times,
    # simply ignore repeated offsets
    if hex(fileOffset) in offsetsDone:
        continue
    offsetsDone[hex(fileOffset)] = True

    g1l.seek(fileOffset)
    header = g1l.read(4)
    if header == "RIFF":
        fileSize = readu32(g1l) + 8
        g1l.seek(0x24,1)
        guid = g1l.read(0x10)
        if guid == "\xD2\x42\xE1\x47\xBA\x36\x8D\x4D\x88\xFC\x61\x65\x4F\x8C\x83\x6C":
            ext = ".at9"
        elif guid == "\xBF\xAA\x23\xE9\x58\xCB\x71\x44\xA1\x19\xFF\xFA\x01\xE4\xCE\x62":
            ext = ".at3"
        else:
            print("Unknown RIFF header with GUID %s" % guid)

    elif header == b"WiiB":
        g1l.seek(0x18,1)
        channelSize = readu32(g1l, False)
        channelCount = readu32(g1l, False)
        ext = ".dsp" #".wiibgm" #.dsp in Romance of Three Kingdoms 12 WiiU?
        fileSize = channelCount * channelSize + 0x800

    elif header == b"WiiV":
        g1l.seek(0xc,1)
        fileSize = readu32(g1l, False)
        ext = ".dsp" #".wiivoice" #.dsp in Romance of Three Kingdoms 12 WiiU?

    elif header == b"KTSS":
        ext = ".ktss"
        fileSize = readu32(g1l, le)

    elif header == b"ATSL":
        # .atsl don't have a size, and entries may point again to a previous
        # subfile (like G1L does), so we can't sum all subfile sizes.
        # Instead, find final (highest) subfile and use offset+size as file end.

        g1l.seek(fileOffset + 0x04)
        headerSize = readu32(g1l, le)
        g1l.seek(fileOffset + 0x0c)
        subfileType = readu32(g1l)
        g1l.seek(fileOffset + 0x14)
        subfileCount = readu32(g1l, le)
        
        subfileLe = True
        if (subfileType & 0x0000FFFF) == 0x0200: # PSP .at3
            subfileLe = False

        entrySize = 0x28
        if (subfileType & 0x000000FF) == 1:
            entrySize = 0x3c

        maxSubfileOffset = 0
        maxSubfileSize = 0
        for j in range(subfileCount):
            g1l.seek(fileOffset + headerSize + j*entrySize + 0x04)
            subfileOffset = readu32(g1l, subfileLe)
            g1l.seek(fileOffset + headerSize + j*entrySize + 0x08)
            subfileSize = readu32(g1l, subfileLe)

            if maxSubfileOffset < subfileOffset:
                maxSubfileOffset = subfileOffset
                maxSubfileSize = subfileSize

        ext = ".atsl"
        fileSize = maxSubfileOffset + maxSubfileSize

    elif header == b"KOVS":
        ext = ".kvs"
        fileSize = readu32(g1l, le) + 0x20

    else:
        print ("Unknown file type %s" % (header))
        continue
    
    g1l.seek(fileOffset)
    if fileCount == 1:
        fileName = os.path.splitext(sys.argv[1])[0] + ext
    else:
        fileName = os.path.splitext(sys.argv[1])[0] + "_%04d%s" % (filesDone, ext)
        if subfolders:
            folder = os.path.splitext(sys.argv[1])[0]
            if not os.path.exists(folder):
                os.makedirs(folder)
            fileName = os.path.join(folder, fileName)
    filesDone += 1

    outFile = open(fileName, 'wb')
    outFile.write(g1l.read(fileSize))
    outFile.close()
    print("Wrote %s" % (fileName))
g1l.close()
