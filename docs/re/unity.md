# HOW TO DECRYPT A MODERATELY COMPLEX UNITY GAME

For some info about AES types: https://github.com/bnnm/vgm-tools/tree/master/docs/encryption/OTHERS.md


## AES USING CSB MODE
Tasked with decrypting Taiko no Tatsujin Pop Tap Beat (iOS) sound files in raw/sound dir, here is how I went to do it For Posterity.

First we determine the kind of file we are dealing with. Easiest way to tell is, open files in a hex editor like HxD. If bytes look too random AKA "too encrypted" (comparing N files don't reveal any patterns) = complex stuff like AES or Blowfish. Files look padded to 0x10, a typical config of AES, so very likely it's that. Other files (outside audio folder) also use a similar encryption, meaning it's something applied over files.

Being (probably) AES, we need the main key (usually same for all files) + IV ("init vector", sub-key per file). In rare cases devs don't use IV, and comparing files will reveal random bytes but files all starting similar. Those cases are manageable (specially if you have a memdump) but not here were all files look different = different IVs.

For those cases we need to reverse the exe with IDA (Ghidra also works but I find it harder to use).
- get the whole game
- this is using Unity, and function/etc names in Unity are saved in an external file, we want those
- load global-metadata.data and Unity exe AKA il2cpp thing (`UnityFramework` in iOS) in https://github.com/djkaty/Il2CppInspector
  - https://github.com/Perfare/Il2CppDumper also works but I used the above as a base
- generate .py for IDA (script that will load names)
- load `UnityFramework` in IDA, use ALT+F7 to run script and select generated .py
  - could have loaded exe in IDA without .py but it's really hard without names
- after a looong while (you need a beefy PC or may take many, many hours) IDA should have named most standard functions

Now we need to poke around to find possible decryption functions. For example try finding ".bin" strings refs, or  functions named "xxxxLoadFile", or "xxcryptxx". After some false leads, we find a good candidate: `SoundManager_ReadAddBanks_2`.

Inside, and near `CriAtom_AddCueSheet` (good, data is probably related to .acb) there is `Cryptgraphy_ReadAllAesBytes` (hmmmmmm) that passes a path to a file (surely those sound/*.bin). Then inside is `File_ReadAllBytes` (aha), and various calls to an `Aes` class (great).

In `Cryptgraphy_ReadAllAesBytes` we see calls to:
- set_BlockSize = 128 (standard of 128-bit = 0x10 bytes)
- set_KeySize = 128 (smallest key of 0x10)
- set_Mode = 1 (from googling this lib's names+enums, ECB = typical AES mode)
- set_Padding = 1 (same, PKCS7 = standard padding)
- set_IV = (see below)
- set_Key = (see below)

First thing this function does after `File_ReadAllBytes` is copying to a buffer (size - 0x10), then copying to another (0x10). Second buffer looks like the IV (standard size of 0x10). Meaning last (or maybe first?) 0x10 bytes in a file are the IV (this is a common way to "hide" the IV). 50% done.

For the key, set_Key uses an array pointer from GetBytes, from a String* returned in `Cryptgraphy_aesKey`. Inside we have a rather complex thing that seems to concat bytes-to-chars to make a final string, this string is then converted again to bytes. Basically we need to find a key-string, then passed as bytes to AES.

Sometimes key is in plain sight as a string/byte array, but here I guess they are doing some obfuscation as we see some byte XORing. Now we do some renaming to try to guess what's going on. Typically in IDA/Ghidra is, go to function, F5 to decompile, put cursor in ugly default names and change labels like "v5" to "str_key" where appropriate, repeat until code is more readable.

More or less it's reading bytes from some address (there is a bit of indirection), XORing with a value calculated per loop up to 16 (calculated to hide actual XOR), converting that to string. Ultimately XOR seems to be `{00 01 01 02 03 05 08 0d 15 22 37 59 90 e9 79 62}` ^ key[i] (after testing all "i" values).

Key address is +184 u8s (or +23 u64s) from "Cryptgraphy__TypeInfo". This __TypeInfo seems to be a pointer to class `Cryptgraphy` (sic), but I'm personally not familiar with this notation (maybe some il2cpp dynamic thing). I assume it points to the "struct Cryptgraphy__Class" but can't find that struct's definition in IDA, but it's on generated `il2cpp.h`, target field being `static_fields` of `Byte__Array *aesVal`.

Now we try to find where `aesVal` is set. Only ref I find it's is new'd in `Cryptgraphy_cctor` then `RuntimeHelpers_InitializeArray_1`. That seems to be a .NET method that points to `qword_2038310` (memory address `0x2038310`, qword=u64 b/c this would be a pointer, since this is a 64-bit exe = 64-bit pointers) and there is some indirect load based on a pointer. I don't know .NET/Unity too much so not sure what's in going on inside. My random guess is, `qword_2038310` will be populated from global-metadata strings/data (or maybe loaded from some MonoBehavior but less likely) then key will be loaded to that.

Just in case I give a cursory look to the global-metadata strings but nothing that pops (it's too big to bother). Out of ideas, but let's not give up yet. IDA doesn't show anything for `qword_2038310` by maybe it's some Il2cpp program issue, so try to find it manually in generated stuff. In generated il2cpp.json we find "2038310". No luck, but close address like 0x2037DF0 do show as strings. Maybe *Il2CppInspector* messed up so let's try *Il2CppDumper*.

That gets us "string.json" and no hits for 2038310 (hex), but 33784592 (int) finds a 0x14 "`PrivateImplementationDetails`" array  `E609C22E1AB9916590F1EA79045BBDAA9EA2FF89`, promising but not our key size (there are similarly named arrays nearby). Seems *Il2CppInspector* needs to generate C# option to show arrays, and even then address doesn't match. Also this array exists as string in global-metadata.

Since *Il2CppInspector* didn't do a great job here, now try reloading *Il2CppDumper*'s script instead (using `ida_with_struct_py3.py`). Now this recognizes the array in Cryptgraphy_cctor and `Cryptgraphy` fields properly. Though in theory *Il2CppInspector* is better, moral of the story is: don't blindly trust tools.

Now let's try to figure out how `InitializeArray` handles the 0x14 text-byte array. From googling `PrivateImplementationDetails` seems it's just a GUID, while the byte array is pointed somewhere else. After trying some stuff now in IDA, we open `dump.cs` from Il2CppDumper (or types.cs in Il2CppInspector), find "E609C22E1AB9916590F1EA79045BBDAA9EA2FF89" and it kindly tells us `Metadata offset 0x2CA14F`. Now hex edit global-metadata, jump to that address, and find a very key-looking string, except some odd chars at the end. After XORing (see above) get get some very key-looking string: "TpFCYkGApUKmHzYz". Good, it "only" took like +10 hours.

Fiiiinally, we try the key with IV as last 0x10 bytes (I used a simple quickbms script). Looks almost correct but first 0x10 are off, meaning we have a wrong IV (IV is only used for light obfuscation, so wrong values aren't fatal). Sigh. Again, we try with IV as first 0x10 bytes aaaaand we got signal, or rather nice .wav/acb.

Fin

```
# Taiko no Tatsujin Pop Tap Beat file (Raw/*) decryptor

# key = "TpFCYkGApUKmHzYz"
set MEMORY_FILE1 binary "\x54\x70\x46\x43\x59\x6B\x47\x41\x70\x55\x4B\x6D\x48\x7A\x59\x7A"

# IV = first 0x10
log MEMORY_FILE2 0 0x10

# rest = data
get SIZE asize
math SIZE -= 0x10

# auto set extension
get NAME basename
string NAME += "."

encryption aes_128_cbc MEMORY_FILE1 MEMORY_FILE2 0 16

log NAME 0x10 SIZE
```

Note that files in /ReadAssets/ go through `DataManager_Awake`, that along the way calls `Cryptgraphy_ReadZipText` then `Cryptgraphy_ReadAllAesBytes`. Meaning files are compressed, use 7Zip to decompress after encrypting. Also note you'll need to rename stuff like .adx to .acb b/c quickbms guesses wrong.

This is a just "moderately complex" case, but other games are *much* harder including encrypted unity exe and/or global-metadata, or even mangled function names (instead of DecryptThing you get TsktueksGnsng). There are ways around that but usually involves Android memdumps, or mad skillz I don't possess.


### Alt method
There is a trick to (sometimes) get easy keys + decryption. Only for AES CBC mode (128, not sure about 256), but most devs don't use ECB or more complex modes anyway:
- make a memdump (while music is playing)
- AES-finder tool to get AES keys from that file
  - https://github.com/astraujums/aes-finder (original)
  - https://github.com/bnnm/vgm-tools/tree/master/misc/aes-finder (compiled)
- Fix/guess IV based on output

The harder part being the memdump (see https://github.com/bnnm/vgmstream/wiki/Android-VM-on-PC).

Due to how AES works keys can be easily found in memory, and even without IV we can recover all of the file except first block (0x10 bytes at the start). However you can get IV like this: "IV = (0x10 start of correctly decrypted data/plaintext) XOR (0x10 start of incorrectly decrypted data)". So if you decrypt without IV (or set to all 0), and know how the first 0x10 bytes look, it's easy to get the proper IV.

Memdumps will give you a bunch of keys (different parts using AES), but files' key is probably repeated a bunch of times, so try those first.
```
# BlazBlue Alternative Dark War
# "5TGB&YHN7UJM(IK<", found in global-metadata too (stringliteral.json)
set MEMORY_FILE1 binary "\x35\x54\x47\x42\x26\x59\x48\x4e\x37\x55\x4a\x4d\x28\x49\x4b\x3c"
# "!QAZ2WSX#EDC4RFV", same (unique IV for all files)
set MEMORY_FILE2 binary "\x21\x51\x41\x5A\x32\x57\x53\x58\x23\x45\x44\x43\x34\x52\x46\x56"

get SIZE asize

get NAME basename
string NAME += ".unity3d"

# when if you don't have IV first time use:
#encryption aes_128_cbc MEMORY_FILE1 "" 0 16

encryption aes_128_cbc MEMORY_FILE1 MEMORY_FILE2 0 16

log NAME 0x0 SIZE
```


## AES IN CTR MODE
Some games use CTR AES mode based on MS's methods, which is slightly more annoying to decrypt.

Example from Shiren 6 unity stuff:

(note, some files just XOR'd the first bytes but they don't have audio so I ignored them)

- use Il2CppDumper with decompressed Switch `main` + `global-metadata.dat` to get script Json DummyDlls
- decompile `main` with IDA (decompress + install DLL plugin to handle Switch's NSO exes)
- wait a long time
- apply `ida_py3.py` and `script.json`
- also wait
- poke around and find `F7_Scripts_AddressablesCustom_SeekableAesStream`, good candidate
  - there is also `XorStream` for simpler xor'd Unity files
- inside it calls `F7_Scripts_AddressablesCustom_SeekableAesStream__bseh` that setups AES:
  - uses `PassWordDeriveBytes(pass, salt)` to get final key
  - aes = AesManaged
    aes.KeySize = 128; 
    aes.Mode = CipherMode.ECB;  //2
    aes.Padding = PaddingMode.None;  //1
  - missing pass + salt
- find calls to `F7_Scripts_AddressablesCustom_SeekableAesStream`
- salt seems to be gotten from `System_IO_Path__ChangeExtension(FileName, 0)` which removes extension from filename
- key seems to be gotten from `PrivateImplementationDetails__67938732_9553_4E8D_AD0F_DED1661FF4EB__a__fk` which is complex and hard to understand where the key is found
- functions that call `Private....__a__fk` are: `fsj__bsdq` and `uk__jfo`
- using `ILSpy` open decompiled `DummyDll/Assembly-CSharp.dll`
- find those clases/functions (just "uk" and "fsj"), they have references to some key-looking value (functions were probably getters)
- both have `DtUp!43AZH46@*fj768GCM@ajNvEdBEB`
- try some simple C# decryptor and see if AES /w and that key/salt works
- doesn't seem to work and returns an block padding error
- all files aren't padded to 0x10 while AES-ECB is padded > must be using AES-CTR mode (stream cypher)
- C# doesn't seem to have a CTR implementation?, reimplement using AES-ECB to make AES-CTR 
- success (returns regular unity files)

See: https://github.com/bnnm/vgm-tools/tree/master/misc/shiren6dec


## Simpler Unity games
Earlier Unity games (like FF Agito) don't actually compile anything and just use original .dll (no global-metadata, small libunity and big Assembly-CSharp.dll).

In those cases just use ILSpy or dnSpy to decompile the .net DLL. Most internal vars and methods and obfuscated with dumb unicode simbols though, but shouldn't be that hard to find decryption methods since class names should be standard.


## FSB Key
Not quite related, but FSB keys in Unity seem to be stored in some resource file like "resources.assets", as plaintext (looking like hex though), near "FMODStudioSettings" strings.
