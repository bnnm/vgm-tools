# PLATFORM ARCHIVES
Tips to extract and play audio files from various archives.

Different consoles have their own main rom/disc format with data. Once extracted you may find regular audio formats or other bigfiles, to be extracted, explained later.


## NES/SNES/GB/GENESIS/etc
Those don't have a standard filesystem nor standard formats. Meaning, most games are different and will usually have chunks of data that the game accesses directly.


## PS1/Saturn/PS2/Gamecube/Xbox/PC/PSP
CDs usually come in .BIN+.CUE archives and DVDs in .ISO.

GC/Xbox use special .ISOs that must be opened with VGMToolbox.

VGMToolbox can also open .CUE for CD games with split tracks.

### PS1 XA audio and .STR videos 
Those must be extracted as *raw* before they are playable in vgmstream. VGMToolbox shows those XA files in green color.

"Raw" files start with 0x00000000FFFFFFFF... (CD sector header). That info is needed to play .XA.
 
However don't extract regular files as raw, and CD sector data is not expected for them.

Note that CDs in .ISO format have that info removed so you can't extract XA from them.

### CD Audio
If the game has CD audio tracks, often you can use .CUE in foobar to read CD audio, then convert to .WAV/FLAC.

An oddity is that some PS1 games access CD directly via CD offsets (LBAs) and not using CD tracks. Meaning they have names (usually .DA) that start in the middle of a CD track.

VGMToolbox can extract those, but CD tracks in .CUE must be merged first. See [binmerge](https://github.com/putnam/binmerge)

### PS1/PS2 with hidden files
Some games somehow don't have any files inside other than a main executable (ex. SPLM_200.10).

That means the game acceses CD/DVD sectors directly. This is often seen in Square Enix or tri-Ace games.

Usually the executable has some index table inside pointing to each file. Files won't have names and are just accesed directly ("open file #1", "open file #1023", etc).

Those must be handled/extracted per game, via some custom .bms/.py/etc.


### CD ALIGMENT AND LBAs
Note that disc-based systems are typically aligned to 0x800 (start at multiples of that) due to CD reader technicallities, meaning new data may start at offsets 0x1000, 0x43D000, etc. Subfiles in bigfiles may also do that.

This is not a hard need, just that CD reads faster like that. You may find "dummy" files for similar reasons.

Each 0x800 block is usually called a "sector", and offsets are often in LBA (logical block addressing) values. Meaning LBA 1 = sector 1 = 0x800 * 1 = offset 0x800. Or LBA 23 = 0x800 * 23 = offset 0xB800, and so on.

Particularly PS2 games often use bigfiles with tables in LBA values rather than plain offsets. This is not a hard need either, probably just that PS2 has APIs that seek to LBAs directly or such.


## WII
VGMToolbox can open .ISO (needs Wii keys?), but there are various compressed formats around:
- .rvz: use DolphinTool from dolphin emu
  -  `for %%x in (*.rvz) do  DolphinTool.exe convert -f iso  -i "%%x" -o "%%x.iso"`
- .nkit: use NKit
  - `for %%x in (*.nkit) do ConvertToIso "%%x" "%%x.iso"`
- .wbfs: use WIT
  - `for %%x in (*.wbfs) do  wit.exe EXTRACT "%%x" out`

## XBOX 360
Use VGMToolbox to open X360 isos. *wx360* may also work.

For DLCs use *wxPirs*.


### XBOX 360 Executables
To decrypt `default.xex` you can use XexTool: `for %%x in (*.xex) do  xextool.exe -e u -c u -o "%%x"_dec "%%x"`


## DS
DS uses ROMs but they do have a filesystem with regular archives. Programs like *ndsts* can open them.


## PSP/PS3 PKG
Those are PSN packages. Use *PkgView* to extract.

## PS3 Discs
As seen in redump sets, may use *PS3Dec*

### Encrypted PS3 EBOOT / DLC
You can use TrueAncestor_EDAT_Rebuilder and TrueAncestor_SELF_Resigner to handle (may need "RAP" keys).


## Vita PKG
```
pkg2zip.exe -x (blah).pkg

psvpfsparser.exe -i (base folder with data) -o (output folder) -f cma.henkaku.xyz -z (zrif key)
```
ZRIF is a long key that starts with `KO5ifR1dQ...`, typically provided with pkg links (can be found by googling too).

It's also possible (but less common nowadays) to find pre-decrypted .pkg under other names like .vpk.

## PS4/PS5 PKG
Use *PkgEditor* and similar tools.

Official PKG (from PSN links) are encrypted with a very complex key. So typically you will use "fake PKG" that are pre-decrypted using a hacked PS4/PS5.

If you can't find a pre-decrypted PKG (or PkgEditor asks for a key) it is impossible to extract that .PKG.

## ANDROID/IOS
They come in .APK or .IPA which are just .zip files. .IPA may be encrypted though.

Sometimes they have an .obb. This can be just a zip, or any binary archive (varies per game).

Many games download data directly to the filesystem and don't have .obb though.



# ENGINE ARCHIVES

## UNITY FILES
Use UnityAssetStudio or some fork (razmoth, YSFC, axix, etc).

Be aware some tools don't extract files correctly. For example, they may write .fsb that are padded with blank data. Those cases are typically rejected by vgmstream and should be extracted with better tools.
