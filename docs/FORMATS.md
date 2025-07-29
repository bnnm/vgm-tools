# STREAMED FORMATS


## KOEI TECMO .SRSA+.SRST (.KTSL2ASBIN+.KTSL2STBIN, .ASBIN+.STBIN, ETC)
The pair is KT's current wave bank. It works like this: game loads `.srsa` in memory then it can play audio inside `.srsa`, or use the info to load streams from `.srst`. (same for .asbin/stbin/etc, they are the same format).

There are .bms and such scripts that can extract data from `.srst`, the results usually playable in *vgmstream*. However I recommend keeping `.srsa`+`.srst` untouched because:
- there are (encrypted) stream names inside `.srsa` (note that names are optional, but bgm usually has them)
- some `.srst` are encrypted, making extracting them a hassle
- some `.srsa` have jingles/music/etc, but can't be extracted (memory/srsa audio is a bit different vs stream/srst audio)

*vgmstream* already handles all that = easier. If you have `BGM.srsa` + `BGM.srst` in the same dir just load `.srsa` and it'll show all audio from BGM.srst with proper names (if names were included).

However one separate problem is that Koei Tecmo's engine often (but not always) uses hashed names, and data is also commonly inside other bigfiles. Meaning you may find `0x3a160928.srsa` and `0x272c6efb.srst` look unrelated but are actually the same pair.

To handle those hashed names so *vgmstream* can play `.srsa`+`.srst` correctly you can do this:
- if you have bigfiles, use [this bms](https://github.com/bnnm/vgm-tools/blob/master/bms/archives/koei_rdb_fdata_file.bms) to extract `.srsa` and `.srst`
  - (or any other tool that works, doesn't matter)
- put `.srsa` + `.srst` in the same dir 
- run [this python script](https://github.com/bnnm/vgm-tools/blob/master/py/archives/ktsl-srsa-srst-matcher.py) to match `.srsa` with `.srst`
  - in some games you may need to edit the .py and set `FULL_MATCH = False` to get a proper match.

This will create a `.txtm` file in the dir that tells *vgmstream* how to match `.srsa` with `.srst`. 

You could also rename the hashed filenames to something more sensical. Reversing KT's hashed names isn't that easy but they reuse names often though: 0x3a160928 = SE1_Common_BGM.SRSA and 0x272c6efb = SE1_Common_BGM.SRST, more or less. [Here](https://github.com/yretenai/Cethleann/tree/develop/Cethleann) are some filelists.

In some cases the .py may not find a match for some `.srsa` no matter the settings. Usually this means the `.srst` is from the localized audio folders, or sometimes it just doesn't exist. For example I've seen `.srsa` in the base game for DLC audio (the `.srst` should be downloaded separately). It could be a bug as well though.


## .OOR (.RIO ENGINE FILES)
rUGP, âge's engine used in a bunch of visual novels (not only from âge) uses custom .ogg called ".oor".

The .rio filesystem in this engine is particularly complex + often has encrypted TOC. Tools like GARBRO only handle early versions, plus it seems like every other game uses a new versions of the engine.

So instead I made a tool that extracts raw .oor from the .rio packages: https://github.com/bnnm/vgm-tools/tree/master/misc/oor-extractor

Example: `oor-extractor game.rio game.rio.002 game.rio.003` (pass all split .rio for best results)

Files aren't sorted in .rio, so one may want to use the `-s xxxx` to filter smaller (voice) files. .oor are playable in vgmstream.


## INTI CREATES BIGRP
Inti Creates use their own sound format called .bigrp, supported by vgmstream. However many games use a fairly annoying encryption (plus hashed names).

I don't know how hashed names work but for encryption and related tools see this:
https://github.com/bnnm/vgm-tools/tree/master/misc/inti

At the top of `intidec.py` is an explanation about decrypting them (it works/needs hashed names).

This changes a bit per game so it can't be exactly automated.


## PC ENGINE ADPCM
PC engine uses ADPCM playable in vgmstream, but it's a bit involved to extract.

See here: https://github.com/bnnm/vgm-tools/blob/master/misc/pcfx/!guide.txt

Resulting ADPCM chunks are playable via TXTH.


## ACB/AWB AND HCA KEYS
Games using CRIWARE (CRI audio middleware) often use .ACB+AWB.

.acb has "cues" (loaded into memory) and .awb "streams". vgmstream can read .awb and use .acb to get names. Some .acb also have data and can be read directly. Meaning you need both.

VGMToolbox can "extract" .hca from .acb/awb but make your life simpler and just play .acb/awb as-is with vgmstream. The format can do non-obvious stuff like having non-standard formats, or encrypting audio, which is handled cleanly by vgmstream.

Sometimes you may find .awb but no .acb. In 99% of the cases you need to dug further as they may not be placed together. For example .AWB in some "streamed" folder and .ACB with other files (loaded in memory), or inside bigfiles. Basically In the CRI engine you load .acb then .acb will call .awb as needed. Programmers can't call .AWB subsongs as far as I know.

However the extra 1% is that (I think) very early versions of CRIWARE did allow playing .awb directly, and some don't seem to have have companion .acb anywhere (even when .acb are used sfx), and do have API functions to handle .awb directly. Gunhound PSP seems to do this, however beyond PSP era games I think those functions were removed.

Do note sometimes .acb don't match .awb 1:1 so vgmstream can use them as-is to get stream names. Those cases are handled via .txtm, that tells vgmstream how to load related .acb: https://github.com/vgmstream/vgmstream/blob/master/doc/USAGE.md#txtm


### UNREAL ENGINE 3 FILES
UE3 packs data .xxx files. In turn, some of those have ".SoundNodeWave" for audio. Those are not actual "files" or "sound formats" but rather "class serializations" with data inside (payload).

Parts of the SoundNodeWave info is external (which fields are used, offsets, etc), and every UE3 version uses slightly different serialization. Meaning, you can't parse it like a common a file.

Instead, use [umodel](https://www.gildor.org/downloads) (UE Viewer or unreal package extractor/decompressor) or similar tool to extract the payload inside .SoundNodeWave. This data can be standard `.ogg`, `.msf`, semi-custom EU3-XMA and so on.

umodel transmogrifies EU3-XMA into riff `.xma` but some custom umodel version can extract them as-is.

Typically 1 SoundNodeWave = 1 subfile, but rarely may have multiple sub-files.

Loop points aren't consistent, some games have extra fields in SoundNodeWave with loops, or may use extra "cue" files for that, or something else.

Also some games use custom UE3 versions (particularly ports to newer hardware) which different compression methods, which umodel may not support. It's possible to make a .bms to extract those packages.


### UNREAL ENGINE 4/5 FILES
Similar to UE4, but data is inside .pak. Inside, audio data (and other types of data) often comes in uexp+uasset, or ubulk+uasset and combinations of that.

Audio data is a bit more varied: .ogg, .awb/acb, .wem/bnk, .ueba, .sab/mab, etc.

Umodel and Fmodel can extract the audio payload from those uexp/uasset/etc. If that fails it's also possible to extract then manually (see vgm-tools/bms). Sometimes a small part of the data payload is inside uexp so you may need both files.

Loops work similarly to that (info inside uexp/uasset or in a "cue" file or anything else). FModel can translate to .json most files so you can check some audio-looking uexp/uasset for info.


### WEM AND BNK (WWISE)
The short version is that games using Wwise load .bnk, then this load plays .wem as needed, sometimes dynamically. So playing just .wem is not usually good enough since things like loops are often in the .bnk.

Because of its dynamic nature vgmstream can't quite handle .bnk. Instead you can use [wwiser](https://github.com/bnnm/wwiser), which will read .bnk and generate .txtp that simulate how Wwise behaves.

Wwiser can also give proper names to bnk+wem rips. .wem files are usually named (number).wem which isn't reversable by itself. If you have a SoundsBankInfo.xml file you may find original .wem names inside but they aren't that useful. Since Wwise's dynamic music is handled via "events", that is wwiser tries to emulate and you can reverse names: [here](https://github.com/bnnm/wwiser-utils/blob/master/doc/NAMES.md) and [here](https://github.com/bnnm/wwiser-utils/tree/master/wwnames). 

Overall wwise games are a pain to rip not just because of this, but rather due the huge number of sounds they have, since they are used for complex sound behaviors. So even if you get names you may end up with thousands of .txtp = thousands of sounds. 

Sometimes wem/bnk are inside .pck, see https://github.com/bnnm/wwiser-utils for .bms to extract them.

## UBISOFT MAP/SB (.SM0+SS0, .SB0+SS0, .SM1+SS0, .SB1+SS1, ...)
This is a database-like format. Open .SM0/SB0 (header) in vgmstream and it should automatically load audio from .SS0 if needed.

Different platforms use other numbers: .SS1, .SS2, .SS3... they work the same.

A problem is that SM0/SB0 may to include thousands of sounds (specially .SM0), including music+sfx+voices. Tools like txtp_maker.py can make filtered .txtp so you can target only the subsongs you want.
 
 
## UBISOFT BAO
BAO (usually .bao) is the evolution of Ubi MAP/SB, but they have many small "header BAOs" that open "stream BAOs".

Extracting BAOs isn't that simple and varies per game. Often they are compressed inside .forge archives (only for games that don't use Wwise). Some info: https://github.com/bnnm/vgm-tools/tree/master/misc/bao

vgmstream supports several versions of BAO, but you need to extract both and open the "header BAOs" which have info about how to play stream BAOs (they can't be supported without header BAOs).

There are no filenames and instead all files are numbers, which must be kept as-is since they files reference each other by number.

Some games also use BAOs in .pk/spk outside .forge archives.

For worse-but-usable results you can also try to use *DecUbiSnd* to play raw stream BAOs.


## FSB AND BANK / FEV
.fsb and .bank are supported by vgmstream, so if one file doesn't play it may be encrypted (or have no audio).

See https://github.com/bnnm/vgm-tools/tree/master/misc/fsb5-keyhelper

Some games use .fev (cue) events to play audio in more complex ways, which could be simulated via TXTP (no tools at the moment).


## MSF + MUS
Those are EA's dynamic music containers, that define N segments + defines info to transition between segments.

The game loads .mpf + some file(s), then it says "play mix 1", "change to mix 2", which will use the appropriate segments in order.

### Mixing .MSF + .MUS
If you only have .MUS, .MSF is usually inside bigfiles (.MSF are files loaded in memory and often lumped with level/engine files, and .MUS streamed files in other folders).

In some cases .MSF and .MUS don't have the same name, and vgmstream can't detect that. You need to make a .TXTM that tells vgmstream how to join both: https://github.com/vgmstream/vgmstream/blob/master/doc/USAGE.md#txtm

### Creating mixes
vgmstream only reads the N segments and not the transition info. You'd need to make .TXTP to join mus+mpf segments.

Help with mixing, this script by Nicknine can read .MPF info for v1 and v5 versions: https://pastebin.com/MVTG1C2K

However most games usually do very simple mixes like segments 1~10 = track 1, 11~20 = track 2 and so on, so you can make .TXTP manually fairly easily.


## VIDEO FILES
VGMToolbox can split many types of videos

FFmpeg as well with the `-acodec copy` option: `for %%x in (*.mp4) do  ffmpeg.exe -i %%x -vn -acodec copy %%x.m4a`

For odd cases there are .bms scripts too: https://github.com/bnnm/vgm-tools/tree/master/bms/demux


## TXTH
TXTH is a way to tell vgmstream how to play raw-ish formats (and more):
https://github.com/vgmstream/vgmstream/blob/master/doc/TXTH.md

If some file.ext has audio and vgmstream doesn't open it as-is, there is a good chance one can make a .txth file to make it playable.

## TXTP
TXTP is a way to tell vgmstream to modify how files are played:
https://github.com/vgmstream/vgmstream/blob/master/cli/tools/txtp_maker.py

More or less per-file config for vgmstream.


## !TAGS.M3U
A way to add tags to vgmstream formats without having to rename files.
https://github.com/vgmstream/vgmstream/blob/master/doc/USAGE.md#tagging
