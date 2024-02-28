CRID USM extractor
v1 by nyaga (https://github.com/Nyagamon)
v2 by bnnm (added new options, xorkey files)
v3 by bnnm (added audio stream selection)
v4 by bnnm (don't decrypt unless key set, read select audio stream name)

Compilation 

g++ "-DLANG_US 1" clADX.cpp clCRID.cpp clUTF.cpp Source.cpp -o crid_mod.exe -static-libgcc -static-libstdc++

****

Some .USM are encrypted using a 64b key (like HCA) so when demuxing the .adx you get bad audio.

How to decrypt:
- unzip CRID(.usm)Demux Tool v1.01-mod
- find game's USM key, often same as HCA key (see hca_keys.h)
  example, in hex: 006CCC569EB1668D
- call crid_mod.exe with key divided in two to extract .adx
  crid_mod.exe -b 006CCC56 -a 9EB1668D -x Opening.usm
- or flags to extract video, info and stuff:
  crid_mod.exe -b 006CCC56 -a 9EB1668D -i -v Opening.usm

If your .usm has multiple audio streams don't forget to use -s N to extract one by one (manually ATM) or you'll get a garbled .adx

If you don't have the USM key you may still be able to decrypt audio.
The key is used to get a 0x20 xor, and .adx often have long silent (blank) parts, meaning easy keys.

- open .usm in hex editor, look for "@SFA" chunks
- if chunk is bigger than 0x140 try to find repeating 0x20 patterns, that's the key
  (encryption is only applied after 0x140, some chunks are smaller than that)
- if no patterns try other videos, silence/blank is often at the beginning or end of files
- save 0x20 pattern key into key.bin
- call CRID:
  crid_mod.exe -m key.bin Opening.usm

Video uses a slightly different method I don't think you can get as easily.

Needless to say you need to original .usm, can't use vgmtoolbox to demux first.

-- bnnm
