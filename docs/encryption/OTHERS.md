# Other types of encryption.

Often games use complex encryption, but there are ways to figure which is being used. That doesn't make it easier to decrypt, but it's a start.

Open the file with *HxD* and use *Analisys > statistics*, shows which bytes are more or less used. If all bytes are used (all bars are almost full) it's using complex-but-standard encryption like AES. Especially if data is padded to 0x10 (an AES particularity).

Conversely if you see lots of 0s used it's probably *not encrypted*. If only certain value is used a lot (like 0x30) it's probably XOR'ed using 0x30, and so on.


## Reversing AES
Typically you need to use IDA or Ghidra to reverse engineer the executable (not for the faint of heart) and figure out the key(s).

Depending on the game, this can be fairly easy (functions are very separate) or nigh imposible (very obfuscated).

For some examples about reversing see: https://github.com/bnnm/vgm-tools/tree/master/docs/re/unity.md


### AES keys
AES have 2 possible key sizes
- 128-bit (0x10): `xsR5TxfhY6sGj6a8`
- 256-bit (0x20): `xsR5TxfhY6sGj6a8xsR5TxfhY6sGj6a8`
- 192-bit: rarely used

A weakness some devs don't realize is that keys often look too much like, well, keys. If you extract all the strings from the .exe and see `xsR5TxfhY6sGj6a8`, that looks suspiciously like an AES key. Meaning you sometimes get the key for free without having to reverse much.

Instead sometimes games may use `banana` and hash it with MD5 to get a 128-bit key, or similar hashes, to obfuscate the key.

### AES modes
There are multiple AES modes which makes figuring:
- AES-ECB: 1 global key 
  - all files start with the same bytes
  - simplest mode, so not very used
- AES-CBC: 1 global key + 1 "IV" (obfuscation vector) per file
  - all files start with the different bytes
  - the IV is often saved in the file itself, or derived from the filename/etc
  - needs the IV to decrypt the first 0x10 bytes, but not the rest (you can set it to 0 to test)
  - most common
- AES-CTR with passwordDeriveBytes: 1 key per file, derived from base key + some per-file value
  - all files start with the different bytes and are not padded to 0x10
  - seen in some .NET/Unity games, not that common

Basically first determine if file has padding to 0x10 (ECB/CBC or CTR) and if data starts the same bytes or not (ECB or CBC).

## Testing keys
Easiest would be with some `.py`. For example:

```
import hashlib, glob, os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

def decrypt_aes(ciphertext, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    #cipher = AES.new(key, AES.MODE_ECB) #uncomment for ECB mode

    plaintext = cipher.decrypt(ciphertext)
    return unpad(plaintext, AES.block_size)


if __name__ == "__main__":
    key = b'xPY8rWHLwhRFGWr8AxUnj8nRA2grZA6E' #256 key
    iv = None #b'....'

    for file in glob.glob('*.bin'):
        with open(file, 'rb') as f:
            data = f.read()
            
            # uncomment if IV is part of data
            #iv = data[0x00:0x08]
            #data = data[0x08:]

        #data = pad(data, AES.block_size) #test stuff
        data = decrypt_aes(data, key, iv)

        with open(file + '.dec', 'wb') as f:
            f.write(data)
```

You can also politely ask chatGPT, Copilot or your favorite IA overlord and they'll regurgitate some valid enough .py too.

First N bytes may be part of the IV or other data that may need to be skipped.

## Other tricks
A trick is running the PC version, or the emulated game and making a memdump (or decompressing save states in some cases).

You can often find partial decrypted assets, or the whole thing if you are lucky. 

Sometimes you even make a memdump per song + extract it from the memdump with a hex editor. Not elegant but who cares.
