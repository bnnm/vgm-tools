# DSF_MAKE 
# - makes .DSF/MINIDSF from full .MLT + .DRV (use mlt_make.py if no .MLT in sight)
# - put dsf_make.py, bin2psf.exe, psfpoint.txt with .MLT/DRV and run (autodetects all .MLT, or drag & drop)
#   * may need to set volume option
#
# =====================================================================================================
# Preliminary MLT--->DSF converter by kingshriek
# This script only supports the Manatee sound driver and not necessarily all the different versions of
# it. For sound data not in .MLT files, convert to .MLT first before using.
# Requires bin2psf & psfpoint.
# =====================================================================================================
# This script produces .dsf/.minidsf files from a Manatee sound driver image and a multi-unit sound 
# data file (.MLT extension) and has similar functionality to the ssfmake script (for .ssf/.minissf). 
# Not all games pack their sound data into .MLT files, and for those that don't, it will require 
# combining the various sound files into an .MLT file before using this script. The individual sound
# formats should have extentions similar to their header strings, only without the leading "S" (e.g. a
# sequence data file will have extention .msb and header string SMSB). See comments below inside
# dsfmake() for information on the various sound formats and header strings.
#
# This script in its current form may not work with some versions of the manatee driver. This is the 
# case since the driver needs to be patched in a few locations so that it doesn't wipe out ripper-provided
# sound commands upon initialization and these patch locations may vary with different driver versions.
# Also, some of these patches disable loading of various default sound data (the driver contains itself
# contains a default DSP program and mixer for instance) so that it uses data in the MLT file instead.
# If a track needs any of this default data, you will need to comment out the corresponding patches in
# dsfmake() for a proper rip.
#
# The bulk of the script is defined as a function, which is called at the very bottom. Feel free to customize 
# this bottom section as you wish. Once good use for it is that you can write some code to loop over a bunch 
# of files and perform the dsf creation in batch mode.
# =====================================================================================================
# Update history:
# 2023-01-26 (v0.04) - python3 (python2 still ok), args, auto mode, fixed volume, cleanup (bnnm)
# 2008-10-14 (v0.03) - Changed the naming behavior of the output file when automatic dsflib/minidsf creation
#                     is turned off so that it doesn't force a .dsf extention (useful for custom dsflibs).
#                     Added a simple utility function that gets the sound RAM offset and allocation for
#                     a given sound data type and bank (useful for custom dsflib/minidsf creation).
# 2008-10-12 (v0.02) - Very minor update. Made it possible to turn off automatic dsflib/minidsf creation.
# 2008-02-16 (v0.01) - Filled in much of the missing information from the initial version - sound data types, 
#                     area map locations, sound commands, driver patches, etc. Added ability to rip one-shot 
#                     data in addition to sequence data.
# 2008-01-12 (v0.00) - Initial version.
# =====================================================================================================
import os, struct, sys, array, glob, argparse, glob, subprocess

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


def get_hdrext(hdr):
    if sys.version_info.major == 2: #?
        return hdr[1:]
    else:
        return hdr[1:].decode('utf-8')

def get_bytes(data):
    if sys.version_info.major == 2:
        data = data.tostring()
    else:
        data = data.tobytes()
    return data

def get_b32(data, offset):
    subdata = data[offset:offset+4]
    return get_bytes(subdata)

def get_u32(data, offset):
    subdata = get_b32(data, offset)
    return struct.unpack('<I', subdata)[0]

#=====================================================================================================

# Converts list of bytes into a sound command array (zero-padded out to 16 bytes)
def sndcmd(x):
    if len(x) > 0x10:
        x = x[:0x10]
    return array.array('B',x + [0x00]*(0x10 - len(x)))


def patch_driver(dsfbin, version):
    # Driver patch for MANATEE.DRV - should cover most versions of the driver
    # Comment any of these out as needed
    NOPtable_versions = {
        0x01: [0x448,0x470,0x488,0x4A4,0x4AC,0x4C4,0x4DC],
        0x02: [0x434,0x4CC,0x4E4,0x500,0x508,0x520,0x538],
    }

    NOPtable = NOPtable_versions.get(version)
    if not NOPtable:
        raise ValueError("unknown driver version")

    NOP = array.array('B',[0x00,0x00,0xA0,0xE3]) # SHx processor ops = 4 bytes
    dsfbin[NOPtable[0]:NOPtable[0]+4] = NOP      # don't clear command area
    dsfbin[NOPtable[1]:NOPtable[1]+4] = NOP      # don't clear MSB banks
    dsfbin[NOPtable[2]:NOPtable[2]+4] = NOP      # don't clear MPB banks
    dsfbin[NOPtable[3]:NOPtable[3]+8] = NOP*2    # don't use default MDB bank 0
    dsfbin[NOPtable[4]:NOPtable[4]+8] = NOP*2    # don't use default MDB bank 1
    dsfbin[NOPtable[5]:NOPtable[5]+8] = NOP*2    # don't use default FPB
    dsfbin[NOPtable[6]:NOPtable[6]+8] = NOP*2    # don't use default FOB


def set_sound_data(dsfbin, datamlt, bank, use_osb):
    ntracks = 0
    # -----------------------------------------------------------------------------------------------------
    # Set sound data
    # MANATEE driver sound data formats identified by header strings:
    #     SMLT - multi-unit archive 
    #     SMSB - MIDI sequence bank 
    #     SMPB - MIDI program bank
    #     SMDB - MIDI drum bank
    #     SOSB - one-shot bank (sound effects)
    #     SPSR - PCM stream ring-buffer
    #     SFPB - DSP program bank
    #     SFOB - DSP output bank
    #     SFPW - DSP work RAM

    sbank_types = (b'SMSB', b'SOSB')    # DSF can either target MIDI sequences or one-shots
    sbank = sbank_types[use_osb]
    # canonical area map offsets 
    areamap = {
       #b'SMLT':0x00000,
        b'SMSB':0x14000,
        b'SMPB':0x14080,
        b'SOSB':0x14100,
        b'SPSR':0x14180,    
        b'SFPB':0x14200,
        b'SFOB':0x14280,
        b'SFPW':0x14288,
        b'SMDB':0x14290,
    }

    nfiles = get_u32(datamlt, 0x08)
    offset = 0x20
    for ifile in range(0,nfiles): 
        fhdr    = get_b32(datamlt, offset+0x00)
        mbank   = get_u32(datamlt, offset+0x04)
        moff    = get_u32(datamlt, offset+0x08)
        msz     = get_u32(datamlt, offset+0x0C)
        foff    = get_u32(datamlt, offset+0x10)
        fsz     = get_u32(datamlt, offset+0x14)

        area_offset = areamap[fhdr]
        #if fhdr in areamap and (fhdr == 'SFPW' or foff >=0):    # write area map data if offset is known
        bank_offset = area_offset + mbank * 0x8
        dsfbin[bank_offset+0x00 : bank_offset+0x04] = datamlt[offset+0x08 : offset+0x0C]
        dsfbin[bank_offset+0x04 : bank_offset+0x08] = datamlt[offset+0x0C : offset+0x10]
        #if foff >= 0 or fhdr == 'SFPW' or fhdr == 'SPSR':    # DEBUG
            #fcon.write('%s: bank=0x%02X offset=0x%06X size=0x%06X\n' % (fhdr,mbank,moff,msz))    # DEBUG

        if fhdr != b'SFPW' and fhdr != b'SPSR' and foff >= 0:    # if DSP work ram or invalid offset, don't write out anything
            if fhdr == b'SMPB' and use_osb:
                offset += 0x20
                continue
            if fhdr == b'SOSB' and not use_osb:
                offset += 0x20
                continue

            dsfbin[moff : moff + fsz] = datamlt[foff : foff + fsz]    # write sound data
            if fhdr == sbank and mbank == bank:    # check specifically for sequence data and get number of tracks
                if ntracks:
                    raise ValueError("multiple ntracks")
                ntracks = dsfbin[moff + 0xC]
                #print('%s data contains %d track(s).' % (sbank, ntracks))
        offset += 0x20
    return ntracks

def validate_drv(datadrv):
    if get_b32(datadrv, 0x00) != b'SDRV':    # header string for sound driver
        raise ValueError("not a valid driver file")

def validate_mlt(datamlt):
    if get_b32(datamlt, 0x00) != b'SMLT':
        raise ValueError("not a valid MLT file")
    chunks = get_u32(datamlt, 0x08)
    size = chunks * 0x20 + 0x20
    if size >= len(datamlt):
        raise ValueError("not a full MLT file (re-extract/use mlt_ext?)")

def prepare_dsf(datadrv, datamlt, naomi):
    validate_drv(datadrv)
    validate_mlt(datamlt)

    szdrv = len(datadrv)
    szmlt = len(datamlt)

    # -----------------------------------------------------------------------------------------------------
    # Prepare DSF and load driver
    if naomi is None: # naomi has bigger ram (untested)
        naomi = (szmlt + szdrv > 0x200000)
    if naomi:
        dsfbin = array.array('B',b'\x00'*0x800000)
    else:
        dsfbin = array.array('B',b'\x00'*0x200000)

    dsfbin[ : szdrv - 0x20] = datadrv[0x20 : szdrv]
    return dsfbin


# don't think bin2psf/etc work with subdirs so use quick hack
def move_file(fname, outdir):
    if outdir == '.':
        return
    if outdir is None:
        outdir = 'dsf'

    try:
        os.makedirs(outdir)
    except Exception as e:
        pass
    
    basename = os.path.basename(fname)
    basepath = os.path.dirname(fname)
    new_fname = os.path.join(basepath, outdir, basename)
    if os.access(new_fname,os.F_OK):
        os.remove(new_fname)
    os.rename(fname,new_fname)
    

def make_dsf(nout, datadrv, datamlt, bank, track, volume, mixer, effect, use_osb, naomi, outdir):
    # -----------------------------------------------------------------------------------------------------
    # Prepare DSF and load driver

    # load sound driver
    #with open(args.ndrv,'rb') as fdrv:
    #    datadrv = array.array('B', fdrv.read())

    # load sound data
    #with open(args.curr_nmlt,'rb') as fmlt:
    #    datamlt = array.array('B',fmlt.read())

    dsfbin = prepare_dsf(datadrv, datamlt, naomi)
    vdrv = datadrv[0x04]    # driver version

    # -----------------------------------------------------------------------------------------------------
    ntracks = set_sound_data(dsfbin, datamlt, bank, use_osb)
    if not ntracks:
        #print("no tracks found with current parameters")
        return 0

    # -----------------------------------------------------------------------------------------------------
    # Set sound commands
    if track is not None:
        ctrack = track
    else:
        ctrack = 0

    scbase_offsets = {
        0x01: 0x13200, 
        0x02: 0x12200,
    }
    scbase = scbase_offsets[vdrv]
    ssbase = scbase + 0x1F0                                                             # SEQUENCE_START track number offset (for minidsf)
    dsfbin[scbase+0x00:scbase+0x10] = sndcmd([0x87,0x00,0x00,0x00,0x00,0x00])           # not sure, but 3rd and 5th bytes have various effects
    dsfbin[scbase+0x10:scbase+0x20] = sndcmd([0x82,0x00, mixer])                        # MIXER_CHANGE
    dsfbin[scbase+0x20:scbase+0x30] = sndcmd([0x84,0x00, effect])                       # EFFECT_CHANGE
    dsfbin[scbase+0x30:scbase+0x40] = sndcmd([0x81,0x00,0xFF])                          # TOTAL_VOLUME
    dsfbin[scbase+0x40:scbase+0x50] = sndcmd([0x05+0x10*use_osb,0x00,0x00,volume])      # SEQUENCE_VOLUME (or OSB_VOLUME)
    dsfbin[ssbase+0x00:ssbase+0x10] = sndcmd([0x01+0x10*use_osb,0x00,0x00,bank,ctrack]) # SEQUENCE_START (or OSB_START)

    # Necessary for sound command processing
    dsfbin[scbase+0x200] = 0x01
    
    # -----------------------------------------------------------------------------------------------------
    patch_driver(dsfbin, vdrv)

    # -----------------------------------------------------------------------------------------------------
    # Write output file
    bout = os.path.basename(nout) #no path
    xout, _ = os.path.splitext(nout)
    
    if use_osb:
        xout += '_OSB'
    bin_name = xout + '.bin'

    with open(bin_name,'wb') as fo:
        fo.write(b'\x00' * 4)    # load address
        fo.write(get_bytes(dsfbin))

    # -----------------------------------------------------------------------------------------------------

    #return
    done = 0
    if track is not None:
        # If track number is explicity given, generate a single dsf/dsflib file
        ext = bout.replace(xout,'')[1:]
        call(['bin2psf', ext, '18', bin_name])
        move_file(xout+'.'+ext, outdir)

        done += 1
    else:
        # Otherwise, automatically create minidsfs based on number of tracks found in bank

        # If only 1 track, create dsf file
        if ntracks == 1:
            call(['bin2psf', 'dsf', '18' , bin_name])
            move_file(xout+'.dsf', outdir)

            done += 1
        
        # Otherwise, create the dsflib file
        elif ntracks > 1:
            # make main dsflib
            call(['bin2psf', 'dsflib', '18', bin_name])
            move_file(xout+'.dsflib', outdir)

            # create minidsfs
            for itrack in range(0,ntracks):
                # final name
                strfmt = ('%02d','%03d')[use_osb]
                fname = ('%s_%02d_' + strfmt + '.minidsf') % (xout, bank, itrack)

                tmp_file = 'temp.bin' #dsf template
                with open(tmp_file,'wb') as fo:
                    fo.write(struct.pack('<I',ssbase+3))
                    fo.write(struct.pack('B',bank))
                    fo.write(struct.pack('B',itrack))

                call(['bin2psf', 'minidsf', '18', tmp_file]) #tmp_file.bin to tmp_file.minidsf
                call(['psfpoint', '-_lib=%s.dsflib' % (xout), 'temp.minidsf']) #point minidsf to lib
                if os.access(fname,os.F_OK):
                    os.remove(fname)
                os.rename('temp.minidsf',fname)
                
                move_file(fname, outdir)
                done += 1

    # -----------------------------------------------------------------------------------------------------
    # Cleanup
    try:
        os.remove(bin_name)
    except OSError:
        pass
    try:
        os.remove('temp.bin')
    except OSError:
        pass

    return done

#=====================================================================================================

def make_tracks(args, datadrv, datamlt):
    return make_dsf(
        args.nout, datadrv, datamlt, 
        args.curr_bank, args.track, args.volume, args.mixer, args.effect, args.curr_type, args.ram,
        args.outdir
        )

def make_banks(args):
    # load sound driver
    with open(args.ndrv,'rb') as fdrv:
        datadrv = array.array('B', fdrv.read())

    # load sound data
    with open(args.curr_nmlt,'rb') as fmlt:
        datamlt = array.array('B',fmlt.read())

    done = 0
    if args.bank is None:
        bank_range = range(0, 0x100)
    else:
        bank_range = [args.bank]

    for bank in bank_range:
        args.curr_bank = bank
        done += make_tracks(args, datadrv, datamlt)
    return done

def make_osb(args):
    done_midi = 0
    done_osb = 0

    if args.use_type is None or args.use_type == 0:
        args.curr_type = 0
        done_midi = make_banks(args)
    if args.use_type is None or args.use_type == 1:
        args.curr_type = 1
        done_osb = make_banks(args)

    return (done_midi, done_osb)

def find_driver(args, file):
    if not args.ndrv:
        test_drvs = ['MANATEE.DRV', os.path.splitext(file)[0] + '.DRV']
        for test_drv in test_drvs:
            if os.path.isfile(test_drv):
                args.ndrv = test_drv
                break
    if not args.ndrv:
        raise ValueError("driver not found (MANATEE.DRV or (file).DRV")
    return 

def make_file(args, file):
    find_driver(args, file)

    args.curr_nmlt = file
    if   file.endswith('.mlt'):
        repl = ('.mlt', '.dsf')
    elif file.endswith('.MLT'):
        repl = ('.MLT', '.DSF')
    else:
        raise ValueError("input file must be .MLT, found %s", file)
    args.nout = file.replace(repl[0],repl[1])

    print("processing: %s " % (file))
    done_midi, done_osb = make_osb(args)
    print("done: %s midi, %s osb" % (done_midi, done_osb))


def test_programs():
    if not os.path.isfile('bin2psf.exe') or not os.path.isfile('psfpoint.exe'):
        raise ValueError("couldn't find bin2psf.exe/psfpoint.exe")

def main(args):
    try:
        files = []
        for file_glob in args.files:
            files += glob.glob(file_glob)

        if not files:
            raise ValueError("no files found")

        test_programs()
    
        for file in files:
            make_file(args, file)

    except Exception as e:
        print("error during process: %s" % (e))

def parse_args():
    description = (
        "Makes DSF from .MLT files"
    )
    epilog = (
        "examples:\n"
        "  %(prog)s  \n"
        "  - makes .DSF from all .MLT\n"
        "  %(prog)s BGM.MLT -t 1 -v 100\n"
        "  - makes .DSF for MLT, first track, volume 100\n"
    )

    ap = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", help="files to match", nargs='*', default=["*.MLT"])
    ap.add_argument("-b","--bank", help="sequence bank number, 0..255 (default: auto)", type=int, default=None)
    ap.add_argument("-t","--track", help="sequence track number, 0..255 (default: auto)", type=int, default=None)
    ap.add_argument("-v","--volume", help="sequence volume\n(255 is max, but it should probably be <= 100 in most cases)", type=int, default=90)
    ap.add_argument("-m","--mixer", help="effect-out mixer select (usually 0x00)", type=int, default=0x00)
    ap.add_argument("-e","--effect", help="DSP program select (usually 0x00)", type=int, default=0x00)
    ap.add_argument("-u","--use-type", help="0: sequence, 1:  one-shot/sfx (default: auto)", type=int, default=None)
    ap.add_argument("-r","--ram", help="0: 2MB RAM, 1: 8MB RAM (Naomi/Hikaru boards)", type=int, default=None)
    ap.add_argument("-d","--ndrv", help="sound driver (default: auto)", default=None)
    ap.add_argument("-o","--outdir", help="output dir (default: auto, use . for current)", default=None)
    # Not sure about any other paramaters yet, especially for sound command 0x87. For others, try editing 
    # the sound commands specified in dsfmake() directly for now.

    args = ap.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()
    main(args)
