# DSF_AUTOTIME
# - times .DSF/MINIDSF
# - put dsf_autotime.py, psfpoint.txt with .DSF/MINIDSF and run (autodetects all .DSF/MINIDSF, or drag & drop)
#
# =====================================================================================================
# DSF/miniDSF auto-timer by kingshriek
# Command-line interface script to automatically time DSF/miniDSF files
# For looping tracks, the script times 2 loops with a 10 second fade.
# Requires psfpoint.
# Caution: this will overwrite the length and fade tags of the specified files
# =====================================================================================================
# 2023-01-26 (v0.02) - python3 (python2 still ok), args, cleanup (bnnm)
# 2008-10-13 (v0.01) - Fixed a really stupid bug in the step calculation for PROGRAM_CHANGE, 
#                      PRESSURE_CHANGE, PITCH_BEND.
# 2008-10-12 (v0.00) - Initial release.
# =====================================================================================================
import argparse, os, sys, zlib, glob, array, struct, subprocess

#=====================================================================================================

def call(args):
    if sys.version_info.major == 2:
        args2 = []
        for arg in args:
            if ' ' in arg:
                arg = '"' + '"'
            args2.append(arg)
        params = ' '.join(args2)
        os.system(params)
    else:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    #print("*call:", arg)

def get_str(elem):
    if sys.version_info.major == 2: #?
        return str(elem)
    else:
        return elem.decode('utf-8')

def get_bytes(data):
    #if sys.version_info.major == 2:
    #    data = data
    #else:
    #    data = bytes(data)
    return data

def get_arrbytes(data):
    if sys.version_info.major == 2:
        data = data.tostring()
    else:
        data = data.tobytes()
    return data

def get_b32(data, offset):
    subdata = data[offset:offset+4]
    return get_bytes(subdata)

def get_b16(data, offset):
    subdata = data[offset:offset+2]
    return get_bytes(subdata)

def get_u8(data, offset):
    subdata = data[offset: offset + 1]
    return struct.unpack('B', subdata)[0]

def get_u32(data, offset):
    subdata = get_b32(data, offset)
    return struct.unpack('<I', subdata)[0]

def get_u16(data, offset):
    subdata = get_b16(data, offset)
    return struct.unpack('<H', subdata)[0]

def get_u16be(data, offset):
    subdata = get_b16(data, offset)
    return struct.unpack('>H', subdata)[0]

def get_s32(data, offset):
    subdata = get_b32(data, offset)
    return struct.unpack('<i', subdata)[0]

#=====================================================================================================

# converts tempo to units of microseconds/quarter-note
def convert_tempo(tempo):
    # algo RE'd from DGconv 0.5 (md5 4354D3C43B45CC42B327E1177DFF8286)
    #   - calculation begins at virtual address 0x402967 (input in EAX), ends at virtual address 0x4029d8 (output in EAX)
    # tempo = tempo * 1001.92 + 0.5
    # tempo = 6.0e3/int(tempo)*10.0e3
    # tempo = 60.0/int(tempo)*1.0e6
    # tempo = int(tempo)
    tempo *= 1000    # This actually seems more accurate (and makes more sense)
    return tempo

# sequence step-time accumulator
# also accounts for tempo - returns time in units of step-microseconds/quarter-note
def autotime_process(trackdata, tempo=0x1F0, offset=0x0C, count=100000):
    extgate = [0x200,0x800,0x1000,0x2000]    # EXT_GATE table
    extdelta = [0x100,0x200,0x800,0x1000]    # EXT_DELTA table
    steps = gate = dgate = 0
    preloopsteps = -1    # -1 used here to indicate no looping
    loop_events = 0

    # Process all sequence events in track data, accumulating the step count
    # Not sure how consistent the Sega Dreamcast's sequence format is between driver versions, but
    # lets just pretend that it is
    while count > 0:
        ctempo = convert_tempo(tempo)    # Convert to microseconds/quarter-note
        event = get_u8(trackdata, offset)
        # Lots of variable length commands here depending on whether gate/step values are to be interpreted as 8 or 16 bits
        if event in range(0x00,0x10):    # NOTE (8-bit gate, 8-bit step)
            step = get_u8(trackdata, offset+0x4) * ctempo
            gate = get_u8(trackdata, offset+0x3) * ctempo + dgate
            dgate = 0
            offset += 5

        elif event in range(0x10,0x20):    # NOTE (8-bit gate, 16-bit step)
                    
            step = get_u16be(trackdata, offset+0x4) * ctempo
            gate = get_u8(trackdata, offset+0x3) + dgate
            dgate = 0
            offset += 6

        elif event in range(0x20,0x30):    # NOTE (16-bit gate, 8-bit step)
            step = get_u8(trackdata, offset+0x5) * ctempo
            gate = get_u16be(trackdata, offset+0x3) + dgate
            dgate = 0
            offset += 6

        elif event in range(0x30,0x40):    # NOTE (16-bit gate, 16-bit step)
            step = get_u16be(trackdata, offset+0x5) * ctempo
            gate = get_u16be(trackdata, offset+0x3)
            dgate = 0
            offset += 7

        elif event == 0x81:    # REFERENCE
            reference = get_u16be(trackdata, offset+0x1)
            refcount = get_u8(trackdata, offset+0x3)
            # Recursively process any nested layers of reference data
            step = autotime_process(trackdata,tempo,reference,refcount)[0]
            offset += 4

        elif event == 0x82:    # LOOP
            loop_events += 1
            mode = get_u8(trackdata, offset+0x1)    # determines whether step is 8-bit or 16-bit
            #print 'DEBUG: loop_events %d' % loop_events
            if loop_events == 1:
                preloopsteps = steps
            if mode < 0x80:
                step = get_u8(trackdata, offset+0x2) * ctempo
                offset += 3
            else:
                step = get_u16be(trackdata, offset+0x2) * ctempo
                offset += 4
            if loop_events > 1:
                step = 0    # step seems to be ignored at loop endpoint

        elif event == 0x83:    # END_OF_TRACK
            break    # end of track reached, stop processing

        elif event == 0x84:    # TEMPO_CHANGE
            tempo = get_u16be(trackdata, offset+0x1)
            #print 'DEBUG: tempo %d' % tempo
            step = 0
            offset += 4

        elif event in range(0x88,0x8C):    # EXT_GATE - I don't think this applies to Dreamcast sequences, but whatever...
            step = 0
            dgate += extgate[event & 0x3]*ctempo
            offset += 1
            count += 1    # EXT_GATE *NOT* included in REFERENCE count!

        elif event in range(0x8C,0x90):    # EXT_DELTA - I don't think this applies to Dreamcast sequences, but whatever...
            step = extdelta[event&0x3]*ctempo
            offset += 1
            count += 1    # EXT_DELTA *NOT* included in REFERENCE count!

        elif event in range(0xA0,0xB0):    # POLY_KEY_PRESSURE
            step = get_u8(trackdata, offset+0x3) * ctempo    # this command probably handles 8-bit or 16-bit step sizes too, not sure exactly how yet
            #print 'DEBUG: POLY_KEY_PRESSURE at offset 0x%05X' % offset
            offset += 4

        elif event in range(0xB0,0xC0):    # CONTROL_CHANGE
            mode = get_u8(trackdata, offset+0x1) >> 7    # determines whether step is 8-bit or 16-bit
            if mode:
                step = get_u16be(trackdata, offset+0x3) * ctempo
                offset += 5
            else:
                step = get_u8(trackdata, offset+0x3) * ctempo
                offset += 4

        elif event in range(0xC0,0xF0):    # PROGRAM_CHANGE, PRESSURE_CHANGE, PITCH_BEND
            mode = get_u8(trackdata, offset+0x1) >> 7    # determines whether step is 8-bit or 16-bit
            if mode:
                step = get_u16be(trackdata, offset+0x2) * ctempo
                offset += 4
            else:
                step = get_u8(trackdata, offset+0x2) * ctempo
                offset += 3

        else:    # OTHER_EVENT
            print('DEBUG: OTHER_EVENT at offset %05X' % offset)
            step = 0
            offset += 1
        count -= 1
        steps += step

    # If the track doesn't loop, add the final gate time
    if count > 0 and loop_events == 0:
        steps += gate + dgate
    return (steps, preloopsteps)   # time and pre-loop time in units of step-microseconds/quarter-note

# get track duration in seconds, accounting for looping and fade
def find_autotime(trackdata, nloops, fade):
    # Get processed times in the track data
    tempo = get_u32(trackdata, 0x08)  # Initial tempo value
    (steps, preloopsteps) = autotime_process(trackdata, tempo)    # step-microseconds/quarter-note
    
    # Assume constant resolution (valid assumption?)
    resolution = 480    # steps/quarter-note

    #print 'DEBUG: resolution %d steps/quarter-note' % resolution
    #print 'DEBUG: steps %d step-microseconds/quarter-note ' % steps
    #print 'DEBUG: preloopsteps %d step-microseconds/quarter-note' % preloopsteps

    # Compute elapsed seconds
    time = float(steps) / float(resolution) / 1.0e6    # seconds
    ptime = float(preloopsteps) / float(resolution) / 1.0e6    # seconds
    if preloopsteps >= 0:    # time looped tracks, subtracting off multiply-counted pre-loop time
        time = nloops * time - (nloops - 1) * ptime
    else:    # for non-looping tracks, add 1 second
        time += 1.0
        fade = 0
    return (time, fade)

#=====================================================================================================

def get_dsf_info(dsfbin):
    # Read through host commands to get sequence bank and track number
    bank = None
    track = None
    osb = False
    # run through command areas of all known driver versions (hope for no false positives!)
    commandlist = dsfbin[0x12200:0x12400] + dsfbin[0x13200:0x13400]
    for k in range(0,64):
        command = commandlist[k * 0x10 : k * 0x10 + 0x10] #0x10 command
        command_id = get_u8(command, 0x00)
        if command_id in (0x01, 0x11): # SEQUENCE_START or OSB_START
            bank = get_u8(command, 0x3)
            track = get_u8(command, 0x4)
            osb = (command_id == 0x11)
            #print 'DEBUG: bank %d, track %d' % (bank, track)
            break
    if bank is None or track is None:
        raise ValueError("couldn't find bank/track")
    return (bank, track, osb)

# extract track data out of sound memory specified by the SEQUENCE_START command in the command area
def get_track(dsfbin, bank, track):

    # Look up sequence bank in area map and extract it
    areamap = dsfbin[0x14000 : 0x14080]
    offseq = get_u32(areamap, 0x8 * bank)
    seqbank = dsfbin[offseq : ]
    szseq = get_u32(seqbank, 0x8)
    seqbank = seqbank[ : szseq]

    # Extract track data from sequence bank
    offtrack = get_u32(seqbank, 4 * track + 0x10)
    trackdata = seqbank[offtrack : ]

    # very small chance of a false positive here - if so, autotime_process will probably crash
    endtrack = get_arrbytes(trackdata).find(b'ENDD')
    if endtrack >= 0:
        trackdata = trackdata[ : endtrack + 0x4]
    return trackdata

#=====================================================================================================

# loads sound memory from file and associated libs into an array
def dsf_load(ndsf):
    szpsfhdr = 0x10    # size of PSF header

    # Initialize sound memory array
    dsfbin = array.array('B', b'\x00'*0x800000)

    with open(ndsf,'rb') as fdsf:
        szdsf = os.path.getsize(ndsf)
        if szdsf > 0x1600000:    # no dsf file should ever be above 16 MB in size
            raise ValueError("unexpected DSF size")
        data = fdsf.read(szdsf)

    # Check for valid DSF header
    if get_b32(data, 0x00) != b'PSF\x12':
        raise ValueError('Invalid dsf file')

    # Get dsflib names (up no 10)
    libs = ['']*9 + [os.path.basename(ndsf)]
    offtag = get_u32(data, 0x08) + szpsfhdr
    if offtag < szdsf:
        tagdata = data[offtag:]
        for k in range (1,10):
            if k > 1:
                sstr = b'_lib%d=' % k
            else:
                sstr = b'_lib='
            offlib = tagdata.find(sstr)
            if offlib > -1:
                sztag = tagdata[offlib:].find(b'\x0A')
                if sztag > -1:
                    tag = tagdata[offlib + len(sstr) : offlib + sztag]
                    libs[k-1] = get_str(tag)

    # Load dsf/minidsf and any dsflibs if they exist
    for lib in libs:
        if not lib:
            continue

        # get lib data
        nlib = os.path.join(os.path.dirname(ndsf), lib)
        with open(nlib, 'rb') as flib:
            libhdr = flib.read(0x10)
            szlib = get_u32(libhdr, 0x08)
            zlibdata= flib.read(szlib)
            libdata = zlib.decompress(zlibdata)

        # copy data into expected DSF part
        szdata = len(libdata)
        offset = get_u32(libdata, 0x00)
        dsfbin[offset : offset + szdata - 4] = array.array('B', libdata[0x4:])

    # too much lib?
    if len(dsfbin) > 0x800000:
        dsfbin = dsfbin[:0x800000]
    return dsfbin

#=====================================================================================================

def dsf_time(ndsf, nloops, fade, multiplier):
    dsfbin = dsf_load(ndsf)
    if len(dsfbin) != 0x800000: #fixed above
        raise ValueError("unexpected unpacked size")
    #with open(ndsf + '.bin', 'wb') as f: f.write(dsfbin)
    
    bank, track, osb = get_dsf_info(dsfbin)
    if osb:
        # no idea about OSB commands so for now use simple default
        minutes = 0
        seconds = 10.0
        fadetime = 0
    else:
        # autodetect using sequence + loop commands
        trackdata = get_track(dsfbin, bank, track)
        time, fadetime = find_autotime(trackdata, nloops, fade)
        if multiplier:
            time *= multiplier
        minutes = time // 60
        seconds = time - 60.0 * minutes
        if seconds > 59.945:
            seconds = 0.0
            minutes += 1

    print('psfpoint "-length=%d:%.1f" "-fade=%d" "%s"' % (minutes, seconds, fadetime, ndsf))
    call(['psfpoint', '-length=%d:%.1f' % (minutes,seconds), '-fade=%d' % (fadetime), ndsf])
    return
#=====================================================================================================

def test_programs():
    if not os.path.isfile('psfpoint.exe'):
        raise ValueError("couldn't find psfpoint.exe")

def main(args):
    if True:
    #try:
        test_programs()
    
        files = []
        for file_glob in args.files:
            files += glob.glob(file_glob)

        for filename in files:
            #if True:
            try:
                dsf_time(filename, args.loops, args.fade, args.multiplier)
            except Exception as e:
                print("couldn't time %s: %s" % (filename, e))
    #except Exception as e:
    #    print("error during process: %s" % (e))

def parse_args():
    description = (
        "DSF/miniDSF autotimer\nCaution: this will overwrite the length and fade tags of the specified files"
    )
    epilog = (
        "examples:\n"
        "  %(prog)s \n"
        "  - autotimes .DSF/MINIDSF\n"
    )

    ap = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", help="files to match", nargs='*', default=["*.DSF","*.MINIDSF"])
    ap.add_argument("-f","--fade", help="fade time in seconds", type=int, default=10)
    ap.add_argument("-l","--loops", help="number of loops", type=int, default=2)
    ap.add_argument("-m","--multiplier", help="time multiplier (use if looped times are off)", type=float, default=1.0)

    args = ap.parse_args()
    return args

if __name__ == '__main__':
    args = parse_args()
    main(args)
