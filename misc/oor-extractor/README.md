Extracts .oor from .rio archives found in âge's rUGP engine games.

.rio has a filesystem with names (SHIFT-JIS), but typically encrypted and reportedly very complex.

Since most .rio unpackers are outdated, this tool simply reads raw data and finds .oor inside.


Example usage:
```
oor-extractor -s 0x10000 muvluv16.rio muvluv16.rio.002
```
