# HCA BRUTEFORCER

Extracts HCA keys from executables or memory dumps and `.awb`/`.acb`/`.hca`.

Take a binary file (exe/memdump) with possible keys and name it `keys.bin`, or make a text file named `keys.txt` with possible text keys, and put it in the folder with 1 *(file).awb/acb/hca* (doesn't matter which, but don't extract `.hca` from `.awb`/`.acb`). 

Then run from the command line: `hca-bruteforcer.exe (file.awb/acb/hca)`.

After a long while (+1GB memdumps may take hours) it should write `HCA BF: best key=NNNNNNNNNNNNNN / HHHHHHHHHHHHHHHH (score=XXX)`. Scores closer to 1 are best, while +3000 are probably false positives (may work in rare cases though).

Make a text file named `.hcakey` and copy `NNNNNNNNNNNNNN`. Try to play the `.hca/awb/acb` file in *vgmstream* and see if it works. (if it did, consider reporting it so it can be added to *vgmstream*).

Also see this a guide: https://github.com/bnnm/vgm-tools/tree/master/docs/encryption/HCAKEY.md

This is a modified version of *vgmstream* with only AWB/ACB/HCA + bruteforce enabled (uncomment `#define HCA_BRUTEFORCE` in `hca.c` + tweak `vgmstream_init.c` + adapt text in `vgmstream_cli.c`), so there is no actual source code.
