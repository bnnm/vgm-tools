# PSB.M
`*.psb.m` + `*.bin` are *M2*'s encrypted and compressed archives.

`psb.m` has names + offsets pointing to `.bin`, that has `.psb`, which usually have audio playable in vgmstream

Tools:
- https://github.com/farmerbb/RED-Project/wiki/Castlevania-Anniversary-Collection
- https://github.com/UlyssesWu/FreeMote/wiki/CommandLine-Usage-for-Tools


Like:
```
MArchiveBatchTool.exe fullunpack --keep alldata.psb.m zlib {key}

PsbDecompile info-psb sound_info.psb.m -k {key-hex}
```

Sometimes one tool works better than the other so try both.

Default (most common) key is `25G/xpvTbsb+6`. Other keys are usually in plain text in the exe, near "*psb*" strings or first strings (decrypt/decompress exe first, for example for `main` use *nsnsotool*).

Instead of zlib other compressions may exist.
