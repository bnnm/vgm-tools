# LINKExtract
#
# Original version by soneek
# v20180320 by bnnm 
#   Modified from G1LExtract

import sys
import os
import struct

def readu32(file, le=True):
    if le:
        return struct.unpack("<I", file.read(4))[0]
    else:
        return struct.unpack(">I", file.read(4))[0] 


if len(sys.argv) != 2:
   print("Usage: LINKExtract infile")
   exit()

infile = open(sys.argv[1], 'rb')
fourcc = infile.read(4)
if fourcc == "LINK":
    le = True
#elif fourcc == "KNIL": #???
#    le = False
else:
    print("Infile is not a LINK file")
    exit()

ext = ".unk"

infile.seek(4)
fileCount = readu32(infile, le)

filesDone = 0;

for i in range(fileCount):
    infile.seek(0x10+i*0x08)
    #print(hex(infile.tell()))
    fileOffset = readu32(infile, le)
    fileSize = readu32(infile, le)
    
    infile.seek(fileOffset)
    header = infile.read(4)
    if header == "_DBW" or header == "WBD_":
        ext = ".wbd" #seen in Bladestorm Nightmare

    elif header == "_HBW" or header == "WBH_":
        ext = ".wbh" #seen in Bladestorm Nightmare
       

    else:
        print ("Unknown file type %s" % (header))
        continue
        
    infile.seek(fileOffset)
    if fileCount == 1:
        fileName = os.path.splitext(sys.argv[1])[0] + ext
    else:
        fileName = os.path.splitext(sys.argv[1])[0] + "_%04d%s" % (filesDone, ext)

    #first wbd then wbh
    if ext == ".wbh":
        filesDone += 1

    outFile = open(fileName, 'wb')
    outFile.write(infile.read(fileSize))
    outFile.close()
    print("Wrote %s" % (fileName))
infile.close()
