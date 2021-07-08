@echo off

set PATH=C:\Program Files (x86)\Git\usr\bin;%PATH%
set PATH=C:\Program Files (x86)\mingw-w64\i686-8.1.0-win32-sjlj-rt_v6-rev0\mingw32\bin;%PATH%

set COMPILE_FLAGS=-Wall -std=c99

gcc %COMPILE_FLAGS%  lzgprs.c -o lzgprs.exe

pause
