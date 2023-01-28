# MLT_MAKE
# - makes .MLT from .MSB/MSP/etc (split banks)
# - put mlt_make.xml with .MSB/MSP/etc and run (autodetects all .MSB/MSP/etc, or drag & drop))
#
#=====================================================================================================
# Sega Dreamcast MLT file creator (ver 0.01 2008-10-14) by kingshriek
# Inspired by MLT Creator.exe tool by manakoAT.
# Creates an MLT file from given Manatee sound data files (FOB, FPB, OSB, MSB, MDB, MPB).
# The resultant MLT file can then be used with dsfmake to produce a DSF rip.
#=====================================================================================================
# 2023-01-26 (v0.04) - python3 (python2 still ok), args, auto mode, cleanup (bnnm)
# 2008-10-14 (v0.01) - Changed the input file syntax, as the previous one interfered with full pathnames
#                      on Windows. Added capability to not include sound data in MLT files but still 
#                      populate the header (can be useful for dsflib/minidsf creation). Made the DSP work 
#                      RAM size user-settable. Added lots of comments.
# 2008-10-12 (v0.00) - Initial release.
#=====================================================================================================
import os, sys, array, struct, argparse, glob

#=====================================================================================================

DRIVER_SIZE = 0x18000    # Size of Manatee driver (upper bound)
DEFAULT_FPW_SIZE = 0x20040    # Use default of 0x20040 bytes for DSP work RAM, the maximum allowed
fpw_size_table = [0x4040, 0x8040, 0x10040, 0x20040, 0]    # Valid sizes for DSP work RAM
#=====================================================================================================

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


# Check allocated DSP program work RAM against DSP program requirements
def check_fpw_ram(mlt_filename, fpw_size, data):
    nfpw = get_u32(data, 0xC)    # Number of DSP programs
    for k in range(nfpw):    # Check all DSP programs in bank
        offset = get_u32(data, 0x10 + 4 * k)    # DSP program offset
        req_index = data[offset+0x20]    # Required DSP work RAM index
        req_fpw_size = fpw_size_table[req_index]    # Required DSP work RAM
        if fpw_size < req_fpw_size:    # Warn user if not enough DSP work RAM allocated
            print('Warning: In %s, DSP program %d requires 0x%X bytes of RAM, but only 0x%X bytes are allocated.' % (mlt_filename, k, req_fpw_size, fpw_size))
            print('         Try increasing DSP work RAM size.')

#=====================================================================================================
# Check total allocated bytes in MLT file
def check_mlt_alloc(mlt_filename, mlt_hdr):
    num_hdr = get_u32(mlt_hdr, 0x8)    # Number of MLT header entries
    hdr_offset = 0x20    # Skip the MLT top header (no allocation info here)
    total_alloc = 0    # Total number of bytes allocated
    for _i in range(num_hdr):    # Check all MLT header entries
        entry_offset = get_u32(mlt_hdr, hdr_offset+0x08)
        entry_size   = get_u32(mlt_hdr, hdr_offset+0x0C)
        entry_alloc  = entry_offset + entry_size
        total_alloc = max(entry_alloc, total_alloc)
        hdr_offset += 0x20

    if total_alloc > 0x200000:   # Warn user if total allocation exceeds total Dreamcast sound RAM
        print('Warning: In %s, total MLT data allocation exceeds 2 MB Dreamcast sound RAM  (%d bytes allocated).' % (mlt_filename, total_alloc))
        print('         Try decreasing DSP work RAM allocation or removing some input files (note: Naomi/Hikaru boards have 8 MB of sound RAM)')
#=====================================================================================================

#=====================================================================================================
# Create MLT header entry
def create_hdr(hdr_bytes):
    hdr = array.array('B', b'\x00' * 0x20)          # MLT header entries are 32 bytes
    hdr[0x00:0x04] = array.array('B', hdr_bytes)    # First 4 bytes are a header string indicating the type of data
    hdr[0x10:0x18] = array.array('B', b'\xFF' * 8)  # Fill MLT offset and size fields with 0xFF (here 0xFF means unused)
    return hdr

# Initialize MLT header
def init_hdr(fpw_size=DEFAULT_FPW_SIZE):
    mlt_hdr = create_hdr(b'SMLT')    # Create base MLT header
    if fpw_size:                                    # If DSP work RAM is to be allocated...
        mlt_hdr += create_hdr(b'SFPW')              # Create DSP work RAM header entry
        mlt_hdr[0x08:0x0C] = array.array('B', struct.pack('<I', 1))             # Set number of MLT entries to 1
        mlt_hdr[0x28:0x2C] = array.array('B', struct.pack('<I', DRIVER_SIZE))   # Place data offset immediately after sound driver
        mlt_hdr[0x2C:0x30] = array.array('B', struct.pack('<I', fpw_size))      # Write in DSP work RAM size
    return mlt_hdr

# Append a single header entry to MLT header
def append_hdr(mlt_hdr, data, hdr_str, bank, include):
    size = len(data)

    tmp_hdr = create_hdr(hdr_str)           # Create base header entry with the given header string
    tmp_hdr[0x04:0x08] = array.array('B', struct.pack('<I', bank))    # Write in bank number
    tmp_hdr[0x0C:0x10] = array.array('B', struct.pack('<I', size))    # Write in number of bytes to be allocated in sound RAM
    if include:    # If the data itself is to be included in the MLT file...
        tmp_hdr[0x14:0x18] = array.array('B', struct.pack('<I', size))    # Write in data size
    cur_entries = get_u32(mlt_hdr, 0x08)

    mlt_hdr[0x04:0x08] = data[0x04:0x08]    # Copy version number from sound data to MLT header
    mlt_hdr[0x08:0x0C] = array.array('B', struct.pack('<I', cur_entries + 1))    # Increment number of MLT header entries
    mlt_hdr += tmp_hdr # Append header entry
    return mlt_hdr

#=====================================================================================================
    
# Apply offsets to MLT header
def apply_offsets(mlt_hdr, offsets, sizes, includes, fpw_size=DEFAULT_FPW_SIZE):
    if fpw_size:    # If we have allocated DSP work RAM...
        hdr_offset = 0x40
    else:
        hdr_offset = 0x20

    hdr_size = len(mlt_hdr)
    void_size = 0  # Void size is the number of bytes allocated in sound RAM that are not included in the MLT file

    for offset, size, include in zip(offsets, sizes, includes): # Loop through data allocations

        #print('DEBUG: offset 0x%06X size 0x%06X include %s' % (offset, size, include))
        chunk_offset = array.array('B', struct.pack('<I', offset + DRIVER_SIZE + fpw_size + void_size))
        mlt_hdr[hdr_offset+0x8:hdr_offset+0xC] = chunk_offset # Write sound RAM offset

        if include:   # If we are including the data in the MLT file...
            chunk_size = array.array('B', struct.pack('<I', offset + hdr_size))
            mlt_hdr[hdr_offset+0x10:hdr_offset+0x14] = chunk_size    # Write offset into MLT file
        else:    # Update the void size
            void_size += size
        hdr_offset += 0x20

    return mlt_hdr

#=====================================================================================================

# Read in data and zero-fill to 32-bit boundary
def read_data(filename):
    with open(filename, 'rb') as fi:
        data = fi.read()
    size = len(data)
    if size % 4:    # If size not multiple of 4
        data += b'\x00' * (4 - (size % 4))  # Zero-fill to the next 32-bit boundary
    data = array.array('B', data)
    return data

# Get data and related information, deal with input syntax
def get_data(filename, banks):

    if filename.find(':::') >= 0:
        # Check first if not including in MLT file
        include = False
        filename, bank = filename.split(':::')
        data = read_data(filename)
        hdr_str = get_b32(data, 0x0)    # Get header-string from data
        if bank:
            bank = int(bank)
        else:
            bank = banks[hdr_str]    # If bank not specified, use the next available bank value

    elif filename.find('::') >= 0:
        # Check second if including in MLT file
        include = True
        filename, bank = filename.split('::')
        data = read_data(filename)
        hdr_str = get_b32(data, 0x0)
        if bank:
            bank = int(bank)
        else:
            bank = banks[hdr_str]    # If bank not specified, use the next available bank value

    else:
        # Default case, include in MLT file, use next available bank    
        include = True
        data = read_data(filename)
        hdr_str = get_b32(data, 0x0)
        bank = banks[hdr_str]    # Use next available bank value
    size = len(data)
    
    #print('DEBUG: hdr_str %s bank %d size 0x%06X include %s' % (hdr_str, bank, size, str(include)))
    return (data, size, hdr_str, bank, include)


# Create MLT file from input files
def mlt_make(mlt_filename, filenames, fpw_size=DEFAULT_FPW_SIZE, base_bank=None, no_header=None):
    mlt_hdr = init_hdr(fpw_size)    # Initialize MLT header, taking into account DSP work RAM size
    mlt_data = array.array('B') #, b'' #empty

    offsets = []
    sizes = []
    includes = []
    
    # Next available bank for each header string
    banks = {
       #b'SMLT'     # multi-unit archive [added manually]
        b'SMSB': 0, # MIDI sequence bank 
        b'SMPB': 0, # MIDI program bank
        b'SOSB': 0, # one-shot bank (sound effects)
       #b'SPSR'     # PCM stream ring-buffer [unneeded?]
        b'SFPB': 0, # DSP program bank
        b'SFOB': 0, # DSP output bank
       #b'SFPW'     # DSP work RAM [added manually]
        b'SMDB': 0, # MIDI drum bank
    }   

    offset = 0
    for filename in filenames:
        (data, size, hdr_str, bank, include) = get_data(filename, banks)    # Get sound data and other useful info
        if base_bank:
            bank = base_bank
        if no_header:
            include = False

        if hdr_str == b'SFPB':    # If data is a DSP program bank...
            check_fpw_ram(mlt_filename, fpw_size, data)    # Check DSP work RAM allocation

        mlt_hdr = append_hdr(mlt_hdr, data, hdr_str, bank, include)    # Append header entry to MLT header

        # Update offsets, sizes, include list
        offsets.append(offset)
        sizes.append(size)
        includes.append(include)

        if include:                 # If we are including the data in the MLT file...
            mlt_data += data        # Append to total MLT data
            offset += len(data)     # Update the MLT file offset
        banks[hdr_str] = bank + 1   # Set next available bank

    # Update sound RAM and MLT file offsets in MLT header
    mlt_hdr = apply_offsets(mlt_hdr, offsets, sizes, includes, fpw_size)

    # Check total MLT data allocation
    check_mlt_alloc(mlt_filename, mlt_hdr)

    # Write out MLT file
    with open(mlt_filename, 'wb') as fo:
        fo.write(mlt_hdr + mlt_data)
    return

#=====================================================================================================

def get_output_name(args, filenames):
    if args.output:
        return args.output
    if not filenames: #?
        return "unknown.mlt"

    # sometimes a single msb (bank) is used for mpb (program), favor the later
    names = [x for x in filenames if x.lower().endswith('.mpb')]
    if not names: #this program is mainly mpb+msb but...
        names = [x for x in filenames if x.lower().endswith('.msb')]
    if not names: #?
        names = filenames
        
    base_file = names[0]
    outname, _ext = os.path.splitext(base_file)
    outname += ".MLT"

    return outname

def make_files(args, filenames):
    mlt_filename = get_output_name(args, filenames)
    file_info = ','.join(filenames)
    try:
        if args.dsp_size < 0 or args.dsp_size >= len(fpw_size_table):
            fpw_size = DEFAULT_FPW_SIZE
        else:
            fpw_size = fpw_size_table[args.dsp_size]
    
        mlt_make(mlt_filename, filenames, fpw_size, args.bank, args.no_header)
        print("done: %s [%s]" % (mlt_filename, file_info))
    except Exception as e:
        print("error processing %s: %s\n [input: %s]" % (mlt_filename, e, file_info))

def detect_files():
    groups = []
    lone_banks = []
    banks = glob.glob("*.MSB")
    
    # find (name).msb + (name).msp + (name)....
    for bank in banks:
        base_name, _ext = os.path.splitext(bank)
        group = []
        for ext in ['.MPB', '.MDB', '.OSB', '.FOB', '.FPB']:
            group += glob.glob(base_name + ext)
        if group:
            groups.append([bank] + group)
        else:
            lone_banks.append(bank)
    
    # find (common).msb + (name).msp + ...
    if len(lone_banks) > 1:
        raise ValueError("couldn't match MSB/MPB (do it manually)")
    for common in lone_banks:
        programs = glob.glob('*.MPB')
        for program in programs:
            base_name, _ext = os.path.splitext(program)
            group = []
            for ext in ['.MDB', '.OSB', '.FOB', '.FPB']:
                group += glob.glob(base_name + ext)
            groups.append([common, program] + group)
    
    return groups

def main(args):
    try:
        if args.files:
            files = []
            for file_glob in args.files:
                files += glob.glob(file_glob)

            if not files:
                raise ValueError("no files found")
            
            groups = [files]

        else:
            groups = detect_files()
            if not groups:
                raise ValueError("no autodetected files found")

        for group in groups:
            make_files(args, group)

    except Exception as e:
        print("error during process: %s" % (e))

def parse_args():
    description = (
        "MLT creator"
    )
    epilog = (
        'Takes common file combos make .MLT (then use dsf_make.py on that)\n'
        'Can also pass files manually. Typical combos:\n'
        '- (file).MSB + (file).MPB + (file).MDB: midi sequence + program + drums\n'
        '- (common).MSB + (file).MPB x N: midi sequences (all) + program\n'
        '\n'
        'examples:\n'
        '  %(prog)s  \n'
        '  - makes .MLT from existing files in dir (autodetects combinations)\n'
        '\n'
        'Sound file syntax (examples):\n'
        '    EXAMPLE.MSB          Use the next available bank, write both header and data.\n'
        '    EXAMPLE.MSB::        Same as above.\n'
        '    EXAMPLE.MSB::2       Use bank 2, write both header and data.\n'
        '    EXAMPLE.MSB:::       Use the next available bank, write header only.\n'
        '    EXAMPLE.MSB:::2      Use bank 2, write header only.\n'
    )

    ap = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", help="files to match", nargs='*', default=None)
    ap.add_argument("-d","--dsp-size", help=(
        "Set DSP work RAM size (default max).\n"
        "Change if script warns about MLT data overflow. Values:\n"
        "- 0: 0x4040 bytes\n"
        "- 1: 0x8040 bytes\n"
        "- 2: 0x10040 bytes\n"
        "- 3: 0x20040 bytes\n"
        "- 4: 0 bytes (no DSP work RAM allocated)"), type=int, default=3)
    ap.add_argument("-b","--bank", help="set bank", default=None)
    ap.add_argument("-o","--output", help="output file (default: auto based on input files)", default=0)
    ap.add_argument("-n","--no-header", help="write header only", default=False, action="store_true")

    args = ap.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()
    main(args)
