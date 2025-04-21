# HCA KEYS
CRIWARE (`.acb`/`.awb`/`.hca`) often uses encrypted HCA audio. When this happen file is 'playable' with *vgmstream* but it sounds garbled.

HCA key are numbers from "1" to "18446744073709551615" (8 bytes in hex: 0xNNNNNNNN NNNNNNNN). It's possible to figure out the HCA *encryption key* and pass the key to vgmstream to make it playable.

**NOTE** this guide is for HCA keys only. If *vgmstream* doesn't not recognize the file to begin with, it may be encrypted in some other way not covered here.

**Important**: don't extract `.hca` from `.awb/acb` to test files. Some `.awb/acb` have a subkey and extracting .hca won't work, just accept `.awb` as-is in your life. This guide assumes `.awb/acb` have `.hca` inside. For `.adx` inside see [ADXKEY.md]


## UNITY WITH CRIWARE INIT
Games using Unity often store keys in plaintext as a string (like "12345").

This string may be in a standard file/mono script called `CriWareInitializer`, near a `StreamingAssets` text inside, inside `level0/level1` (or other early `levelX`), `globalgamemanagers`, `resources.assets`, `unity default resources`, `000...000` and such (there is no standard place).

A simple way to find it is including most files in a .tar/.zip (set *no compression*) then searching for `StreamingAssets` text (may appear in multiple places). Sometimes Unity uses compressed assets and you need to decompress first though (string may become `SteamingAs`+bytes), though a key string shouldn't be compressed so even with a hex editor it's pretty easy.

Alternatively, load files in Unity AssetStudio (https://github.com/Perfare/AssetStudio) and find *CriWareInitializer*. Then select it, `extract > raw > selected assets`, open with a hex editor and see if key is near `StreamingAssets`.

Sometimes key in *CriWareInitializer* is not set or set but not used (or there are multiple keys), see below.


## UNITY WITH GLOBAL METADATA
Sometimes key is inside `global-metadata.dat` (a companion file in `/Data/Managed/Metadata/`). Get Il2CppDumper (https://github.com/Perfare/Il2CppDumper), find game's Unity main (typically `GameAssembly.dll` or `libil2cpp.so`, not a base .exe) plus `global-metadata.dat`. Then launch `Il2CppDumper.exe`, select main exe and metadata. This should make a bunch of files.

Now open `stringliteral.json` with a text editor, and it may contain the actual key somewhere. We want to look for text text that could be an HCA key. For example `"value": "123456789"` 123456789 could be the key.

If you have *notepad++*, open the *find dialog* (CTRL + F), change the *Search Mode* radio button to *Regular expression*". Then put `"[1-9][0-9]+"` or `"[1-9][0-9]{6,19}"` in the *Find what" box, then press **Find Next**. That will find next key-looking string (keep pressing the button as there will be multiple cases).

Another option is using *notepad++*'s *edit > line edit operations > Sort Lines Lexicographically Ascending*, which groups numbers together. Look for `"value": "..."` strings. If you have grep.exe (included with GIT, set in path) you can also use `grep.exe -Eo '[1-9][0-9]{4,19}' stringliteral.json > keys.txt`..

With the above methods find numbers that look big enough (tiny numbers like "32" are unlikely to be keys) and test them as detailed below. It's a bit cumbersome but there shoulnd't be that many.

You can also copy all keys (withouth " quotes) to `keys.txt` and test many keys at once with the hca-bruteforcer.

Sometimes main is encrypted/obfuscated and needs to be decrypted first before it can be used with Il2CppDumper (TODO). 

If that also fails sometimes key is inside another script or text file. You could .zip all unity files with no compression + use strings2.exe + grep (see above). But key may be as part of game code which requires more complex methods so this rarely works.


## EXTRACTING FROM BINARIES / MEMORY DUMPS
In some cases the key may be in main .exe/dll/so/eboot.bin and similar executable (possibly obfuscated). Manual reverse engineering takes a lot of time, but we can semi-brute-force it instead. It's a bit slow and more involved but works very often.

Get hca-bruteforcer [here](https://github.com/bnnm/vgm-tools/tree/master/misc/hca-bruteforcer) + some .awb/hca, then put a "key file" (see below) in the same dir. Then run: `hca-bruteforce.exe (file)`. After a while it may write `HCA BF: best key=XXXXXXXXXXXXXX / XXXXXXXXXXXXXXXX (score=XXX)`. Scores closer to 1 are best, while +3000 are probably false positives (may work in rare cases though).

To make a "key file", you have 3 ways (bruteforcer will try all if found):
- text list: use strings2.exe on some exe/.so/etc or memdump and rename output to `keys.txt` (fast but works less often).
- binary list: rename .exe/.so/etc or memdump to "keys.bin" as-is (may take a few hours depending on the keys.bin size).
  - bruteforcer will try multiple modes but usually only `64LE` or `32LE` (rarely) matter, you may close it early.
- classic bruteforce: make a file named `keys.num`. This starts the typical "try every number until end". 64-bit keys are not feasible to reverse, but rarely devs are dumb enough to use 32-bit keys, which is doable in a few hours.

I recommend trying executables as keys.bin first. Works well for custom or UE exes, while Unity exes having keys is less common. Switch exes (`main`) must be decompressed first with programs like `nsnsotool`. Protected exes (such as iOS) may sometimes work too as keys can be in a non-encrypted section. Some games (Switch particularly) read/join keys from several commands, which this bruteforcer can't handle though.

If that fails make a memdump + rename to `keys.bin`, which is often the best way to find keys. First play until the game is playing some SFX or BGM (ex. title screen), key should be in memory at that point. Then:
- Windows games: open the task manager, right click on process > make memory dump > accept open folder. 
  - Note this dump may contain crap from your system so don't go around sharing it too casually.
- Switch games: I've had some success using a Switch emu and dumping its memory like described above
- Android games: you can probably use one of those malware-ridden emus like BlueStacks, or a rooted phone.

Memumps work very often, but clever devs can work extra hard agains it so it isn't 100% safe. Also dump memory shortly after game is initialized and not much has happened to minimize chances of key erased and memdump is smaller.

### Android memdumps
Some info since they are most common but harder to make memdumps.
- Dump with a rooted phone + GameGuardian, but some games detect it
- Longer version that works more often: (ask nicely and not too often and I can probably do it myself)
  - root + magisk w/ Zygisk + Shamiko + Universal SafetyNet Fix
  - get `dumpdroid` (https://github.com/tkmru/dumproid or find alt)
  - `adb push dumproid /data/local/tmp/dumproid` (NOT to /sdcard/, can't change permissions there)
  - `adb shell` + `su` + `chmod u+x /data/local/tmp/dumproid`
  - `ps -A | grep (game ID like com.banana.name)` to get PID
  - `/data/local/tmp/dumproid -p <PID>`, will write memdump to `/data/local/tmp/xxxxxxxxxxxxxx`
  - copy to PC with `adb pull /data/local/tmp/xxxxxxxxxxxxxx` or *FTPDrod* or something


## EXECUTABLES
If all of the above fails you can use https://github.com/djkaty/Il2CppInspector or https://github.com/Perfare/Il2CppDumper + IDA/Ghidra to get keys:
- unzip, open
- drag global-metadata.dat + unity exe (`GameAssembly.dll`, `libil2cpp.so`)
- select "python script for disassemblers", press export to generate il2cpp.py/.json/.h
  - Il2CppDumper generates a similar .py but haven't tested it
- load exe/dll/etc in IDA
- after base import (can be done before full auto analysis), press ALT+F7 / run script
- select .py, wait a long while
- find calls like CriAtomExAcb_Decrypt, CriWareDecrypter_Initialize and so on and see where are they called and params = keys
  - ex. CriAtomExAcb_Decrypt loads keys in code [ALTDEUS (PC)]
  - ex. CriKey__Get (used after CriWareDecryptedConfig__ctor, inside some sound init function) manually transforms 2 ints to strings and concats them for the final key [TouHou Danmaku Kagura (Android)]

For regular .exes Ghidra/IDA also work but no function names = harder. Try looking for `CRIWARE: blah blah` error strings instead.

In rare cases global-metadata.bin is XOR'ed/encrypted and needs to be fixed first. Sometimes it's easy enough, others one could try reversing libunity.so/UnityPlayer.dll/etc, that usually loads and decrypts it (look for "global-metadata.dat" strings). Or can make a memdump and look for the decrypted global-metadata.bin. Metadata usually starts with AF1BB1FA 18000000 (unity ID + version), but in some case (obfuscation?) ID can be null: 00000000 18000000. Max can be found like: (offset at 0x108) + (size at 0x10c).


## TESTING
Copy the numeric keystring to a txt file (don't add a new line/enter), for example just `123456789`. Then rename it to `.hcakey` (dot + extension). Earlier Windows versions may need an extra dot to rename it correctly: `.hcakey.`.

Play with vgmstream (again, use the .awb/acb instead of extracting .hca) and see how it goes. Wrong keys will give mostly silent files with a bunch of clicks.


## SHARING
If all went well and you got the key, be cool and post it in some forum thread or discord or commit to github (https://github.com/vgmstream/vgmstream/blob/master/src/meta/hca_keys.h) so everybody can benefit from your work.
