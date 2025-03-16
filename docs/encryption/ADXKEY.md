# ADXKEY
ADX may be encrypted like HCA is.

You can try most of the methods (find key string in ), but for older games or if your .awb has ADX is inside you'll need this instead:
- extract internal .adx first (hex edit or use vgmtoolbox's adx extractor)
  - remember it's best to keep/use the `.awb` once key is found/added
- get VGAudio's `VGAudioTools.exe`
  - https://github.com/Thealexbarney/VGAudio/releases/tag/v2.2.1
- use `VGAudioTools.exe CrackAdx file.adx`
- should write one or two keycodes
- make a file named `.adxkey` and copy keycode as plain text
  - .adxkey works with `.awb` as well

Due to technical reasons sometimes this may not be the exact keycode the game uses. For preservation purposes see HCAKEY.md and try to find the original key too. If you can't and are commiting this key to vgmstream remember to make a note about not being the real key.
