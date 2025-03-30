# FSBKEY
If you can't play some `.fsb` or `.bank` in *vgmstream* files may be encrypted with a key (fairly easy to crack). Use a hex editor to check there isn't `FSB` or `RIFF` somewhere.

Helper tools:
- FSB3/4: https://github.com/hcs64/vgm_ripping/tree/master/decryption/guessfsb
  - https://hcs64.com/files/guessfsb03.zip
  - https://hcs64.com/files/guessfsb031.zip
  - https://hcs64.com/files/guessfsb04beta.zip
- FSB5: https://github.com/bnnm/vgm-tools/blob/master/misc/fsb5-keyhelper/fsb5-keyhelper.py 


FSB5 was introduced in ~2009, but FSB4 is common until ~2016, so you may need both. `.bank` should be FSB5 only.

Use the tools to find 
Once you have the key it can be included in vgmstream (post it somewhere devs can see it), or you can make a file named `.fsbkey` with the key in plain text in the folder where `.fsb`/`.bank` are, then open `.fsb`/`.bank`.


## FSB5
There is a guide on top of *fsb5-keyhelper.py*,  but basically:
```
fsb5-keyhelper.py (file)
```

Open generated `(file).bin` with a hex editor and try to find (parts of) key in plain text somewhere inside.


## FSB3/4
`guessfsb.exe (file)` and wait a while.

*guessfsb031* supports `--write-key-file`, for games like some Guitar Hero that have a key per file:
````
for %X in (*.fsb.xen) do guessfsb.exe %X --write-key-file
```

Otherwise try *guessfsb04beta* which may be slightly better.

If the tool hangs or doesn't find anything try: `fsb5-keyhelper.py (file) -t 4` for FSB4 and see FSB5 info above (encryption is the same, just the header is different). For FSB3 `-t 3` also works, but FSB3 are simpler and you can see patterns as-is with a hex editor.


## Unity
Not very important since key is easy to crack, but FSB keys in Unity seem to be stored in some resource file like "resources.assets", in plaintext (looking like hex though), near "FMODStudioSettings" strings.
