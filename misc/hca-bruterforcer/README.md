# HCA BRUTEFORCER

Extracts HCA keys from executables or memory dumps and coms .awb/.acb/.hca.

Make a binary key file and name it `keys.bin`, or a text file named `keys.txt`, then `hca-bruteforcer.exe (file.awb/acb/hca)`

Also see this a guide: https://github.com/bnnm/vgm-tools/tree/master/docs/encryption/HCAKEY.md

This is a modified version of *vgmstream* with only AWB/ACB/HCA + bruteforce enabled (uncomment `#define HCA_BRUTEFORCE` in `hca.c` + tweak `vgmstream_init.c` + adapt text in `vgmstream_cli.c`), so there is no actual source code.
