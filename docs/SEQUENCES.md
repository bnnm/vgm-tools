# STREAMED AND SEQUENCED AUDIO
Most consoles use "streamed" (prerecorded) files. Take a file from the game as-is, play it with vgmstream and get audio  exactly like it sounds in-game

Older consoles use *sequenced* audio (like a special MIDI), playable with .SPC, .NSF, .GBS, .VGM, .UTF, .PSF... Also see [here](https://github.com/vgmstream/vgmstream/blob/master/doc/USAGE.md#sequences-and-streams). Those are often not plain files in the games. So "how to extract .PSF from game X" is meaningless as .PSF are *manually created* and don't exist in the files.

These docs only cover streamed audio, but here is some info for posterity.

Typically sequenced console audio is not "extracted", but instead "made" using parts of the ROM (like an emulator savestate) with extra data stripped, then made playable in a standalone plugin/player. This player is actually an emulator with graphics/control/etc code removed.

Often you end up playing an actual mini-rom. So these files are pretty accurate, but can be hard to make.

General types:
- dumped: emulators can dump those custom files during gameplay
- logged (.VGM): must be "recorded" during gameplay
- *SF formats: take sequence files + sound banks + main program/driver, and stick them together
  - for games that use standard drivers, tools like VGMToolbox, DSF, etc, that can make them
  - for games that use custom drivers, you will need to learn console's CPU assembly to make them (seriously)

For some sequenced files there are tools that can open them directly and simulate sequence engines (rather than emulating the whole thing): Factor 5's Musyx, Procyon's DSE, GC's JaiSeq, Nintendoware, etc. Those are less common and hard to make as well.
