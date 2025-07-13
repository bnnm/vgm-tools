# Sega Saturn game reversing engineering tips

Simple stuff I figured out while poking around, may contain errors.

Steps are for Ghidra but IDA may work too (SH3/SH4 CPUs may be backwards-compatible?).

Beware! Ghidra's decompilated pseudo-code can be wonky (for Saturn at least) and will sometimes skip important instructions (like a buf increasing +1). Mainly seems to be confused by delayed instructions(?) after return, like `rts; _add 0x2,r2`. Also sometimes Ghidra identifies 2 functions where there is only one:
- function1 does:  (op cluster1), then (op cluster2), optionally jumps to (op cluster2) in the beginning
- Ghidra sets (op cluster2) as a function2, but also shows both clusters as part of function1
- renaming labels get quite strange as it affects both function1 and function2

So, just ok as a guide for the disassembly.

## Manual exe loading
- get latest Ghidra
- load main exe (first file in CD, like 00LOAD.BIN) in Ghidra
- manually select processor: SH2
- manually select load address in *options*, usually `06004000`
  - could be `06001000`, `06010000`... depending on game, see below for savestate tips to get correct address
  - wrong values still decompile, but jumps/offsets may be wrong (exes may store fixed `060xxxxx` addresses)
- Ghidra may be able to autodetect
- if autodetect failed (gives wonky/few functions):
  - move to entry function (usually at 0), press D to decompile
  - if that fails, probably means that isn't the entry point, must find
- SH2 instructions have always size 16b BE
  - go to a bunch of 16-bit values, press D at an aligned address (try align 0x04 just in case) and see if Ghidra figures out
  - Ghidra seems to figure out ok based on jumps etc even if not set at a function start, keep mashing that D
- often Saturn games have multiple exes (.BIN) so this isn't too useful
  - probably can be fixed by manually loading more exes in proper locations, see below instead

## Savestate loading
- get and install Ghidra's Saturn plugin
  - https://github.com/VGKintsugi/Ghidra-SegaSaturn-Loader
- make a mednamed emu savestate
  - open file with mednafen
    - drag and drop .cue into exe works
  - play until desired point
  - press F5
  - go to "`mcm`" (what) dir and get .mcm savestate
  - unzip savestate
- load unzipped savestate in Ghidra
- see "Work_RAM_High" area for (most likely) code
- try autoanalysis or move to entry point, press D
  - also see emu tips below for actual addresses
- yabause save states also work, may be less correct?
  
  
## Emu debugging
- savestate loading + seeing debug addresses = easier Ghidra decompilations
- open file with mednafen
- move to desired debug moment
- press ALT+D, this starts debugger (while game is running)
  - https://mednafen.github.io/documentation/debugger.html
- font is tiny!
  - close mednafen
  - open mednafen.cfg
  - change `ss.debugger.disfontsize` to 6x13 or 9x18 (registers will be tiny still)
- basic debugger controls: 
  - press S to step (execute single intruction)
  - R to continue (play until next breakpoint)
  - SPACE to set a breakpoint (stops when CPU goes there)
  - T to change CPU (IMPORTANT!)
  - G goto line
- T changes between Saturn's two SH2 CPUs
  - sometimes one SH2 does graphics, other audio
  - so one CPU won't reach certain code places/breakpoints
- where to look? 
  - there is a "jump address list" below (as NNNNNN > NNNNNN ... NNNNNNN > NNNNNN and so on)
  - press S at random times and see which address it stops
  - you can use this as a reference in Ghidra, go there, press D, etc
  - ex. in MvsSF, T to change to audio SH2, S usually lands in ~0600d1xx, 
    - that seems to be a control function, and jump addresses/steps would land into 0600d676 = decoder
- mix ghidra and debugger for better results
  - ghidra decompiles some function, pseudocode get
  - in debugger go to that address and put breakpoint
  - play a bit until breakpont triggers (may need to change CPU with T)
  - step that function in emu to see register values
