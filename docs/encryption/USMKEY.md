# RECOVERING USM KEYS
Sometimes .usm videos are encrypted and that's no fun. You can use crid_mod to decrypt+extract video like this:
```
crid_mod.exe -b 00BD86C0 -a EE8C7342 -v -x -i file.usm
```
Where key=64b hex, -b=upper 32b, -a=lower 32b.

If you don't have the key don't despair yet. First try the game's HCA/ADX key (see [hca_keys.h](https://github.com/vgmstream/vgmstream/blob/master/src/meta/hca_keys.h)/[adx_keys.h](https://github.com/vgmstream/vgmstream/blob/master/src/meta/adx_keys.h)) as some devs reuse them. Also rarely no key (`crid_mod.exe -v -x file.usm`) or key 0 (`crid_mod.exe -b 00000000 -a 00000000 -v -x file.usm`) works. If that doesn't work either keep in mind keys are typically in the .exe or base CRI files in Unity's case (in plain text) so poke around there with some tools too. 

Still no key? There is also a way around that (could be automated but quick explanation for now):

.usm keys become 2 0x20 video XORs, and 1 audio XOR. This XOR generation is pretty dumb, so if original data has blank or guessable parts it's possible to recover the original key from videos alone. Get crid_mod (https://github.com/bnnm/vgm-tools/tree/master/misc/crid-mod) to demux/test and for the source.

First open `clCRID.cpp`, lines after ~295 contain how data is XOR'ed (keep it around to cross ref). In code `k1` is flag `-a` = lower key, `k2` is flag `-b` = upper key, as uchar = LE (key `00DDEEFF00AABBCC` becomes `k1[4]= CC,BB,AA,00` / `k2[4]=FF,EE,DD,00`).

Now find some `@SFA` audio frame with repeating 0x20 XOR patterns, usually seen in silent/blank audio parts in the beginning/last frames. XOR is only applied after 0x140 bytes from `@SFA`, take the XOR (aligned)

Given how this XOR is generated (line 341) we can get even bytes of the original key. Basically first 8 even bytes XORed with ^ 0xff +- some value = first even bytes in key (as LE).
```
key[0] = t[0] ^ FF
key[2] = t[2] ^ FF
key[4] = t[4] ^ FF - f9
key[6] = t[6] ^ FF - 61

ex Okami HD audio XOR:
9A559E52 94553343 37556152 9A559B43 3D550652 C655C043 0655F152 8455CC43

9A ^ ff = t[0] = 65 = k1[0] // t[0] ^ FF
??
9E ^ ff = t[2] = 61 = k1[2]
??

94 ^ ff = 6B = t[4] = 6B - F9 = 72 = k2[0]
??
33 ^ ff = cc = t[6] = cc - 61 = 6B = k2[2]
??

thus partial key: xx6Bxx72 xx61xx65
```

Now demux video with partial key + 0s: 006B0072 00610065. If demuxed video's header has metadata, open with hex editor and you'll see something partially readable.

From this point, easiest is trying some values for second byte (006B0072 00618065, 006B0072 00616065) until some more of the metadata reads correctly (in case of Okami HD, there are "`TMPGEXS 00000028IDCPREC 0000000800000003TMPGEXE`" strings for easy comparison). Then take the exe/binary and find first bytes (ex. xx616765 > find 656761 as LE, or 616765 are BE >> final key 006B6172 61616765). With some luck you'll find the actual key lying around (curiously enough in Okami HD key is "karaage" in ASCII which actually was PS2 Okami ADX key).

If that didn't work we can derive the key undoing video XOR too (even without without audio unXORing), but it's more time consuming, probably could be automated though.

Find first `@SFV` video frames after "#METADATA END", that should contain metadata part of demuxed video. Video frames apply XORs after 0x40 *if* `@SFV` size is >=0x200 (see code), so if first SFV is smaller this makes it a bit harder and you may need to find another frames with previsible output (try last ones).

But as long as we know original output (for example Persona5/Royal we can compare unencrypted vs encrypted videos) we can undo the 2 video XORs figuring out most t[i] by steps, in turn getting missing k1/k2 bytes (again refer to clCRID.cpp, long to explain).

Or just keep trying bytes until demuxing reads clearer and clearer, it's easy enough since we can pinpoint ranges that give slightly better output (ex. 0x60 gives better results than 0x20, so byte could be between 0x50~0x70). Note that upper bytes are sometimes 0s so if after audio XOR you have xx00xx00 xxAAxxBB key is likely just 0000000 xxAAxxBB = easy times.

There is a simpler way to decrypt it if you only want audio and video uses ADX, see `crid_mod`'s readme.