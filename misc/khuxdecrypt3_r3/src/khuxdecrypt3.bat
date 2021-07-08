@echo off
set PATH=C:\Program Files (x86)\mingw-w64\i686-8.1.0-win32-sjlj-rt_v6-rev0\mingw32\bin;%PATH%
set COMPILE_FLAGS=-Wall -std=c99
REM set LINK_FLAGS=-L. -lzlib1 
set LINK_FLAGS=


gcc %COMPILE_FLAGS%  khuxdecrypt3.c chacha.c miniz.c lodepng.c %LINK_FLAGS% -o khuxdecrypt3.exe

gcc %COMPILE_FLAGS% -D_FILE_OFFSET_BITS=64 khuxdecrypt3.c chacha.c miniz.c lodepng.c %LINK_FLAGS% -o khuxdecrypt3_64.exe

pause
