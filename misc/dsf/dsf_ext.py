# DSF_EXT
# - extracts DC/Naomi data from raw files
# - for Naomi isos, convert to .gdi, extract (NAME).BIN, decrypt it (DEScrypt), and use dsf_ext.py over .dat
# - for DC isos, convert to .gdi and extract normally (no need to use this tool)
# - for Atomiswave isos, use atomiswave.bms on track03 (no need to use this tool)
#
# =====================================================================================================
# Sega Dreamcast MLT/data extractor by kingshriek
# Command-line interface script to extract data out of a file/archive
# =====================================================================================================
# Update history:
# 2023-01-26 (v0.03) - python3 (python2 still ok), args, multiple types, cleanup, fused mltext+dsfsndext (bnnm)
# 2008-10-12 (v0.02) - Added __name__ == '__main__' statement. Script will now create output directory
#                   if it doesn't exist.
# 2008-02-17 (v0.01) - Added SPSR to allowable header list. Changed output to only display non-null banks.
# 2008-01-12 (v0.00) - Initial version.
# =====================================================================================================
import argparse, os, sys, mmap, glob, struct, binascii

#=====================================================================================================

def get_bytes(data):
    #if sys.version_info.major == 2:
    #    data = data
    #else:
    #    data = bytes(data)
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

def get_u16(data, offset):
    subdata = get_b16(data, offset)
    return struct.unpack('<H', subdata)[0]

# sizes/offsets are signed
def get_s32(data, offset):
    subdata = get_b32(data, offset)
    return struct.unpack('<i', subdata)[0]

#=====================================================================================================

def save_file(fimap, outdir, basename, index, ext, offset, size, info):
    foname = '%s_%03d.%s' % (basename, index, ext)
    print('%s [0x%08X]: %d bytes - %s' % (foname, offset, size, info))

    path_foname = os.path.join(outdir, foname)
    with open(path_foname,'wb') as fo:
        data = fimap[offset : offset + size]
        fo.write(data)

def spsd_test(fimap, file_size, offset):
    size = get_s32(fimap, offset+0x0c)
    if size < 0x40 or size > file_size:
        return 0
    if size == 0x00FFFFFF:
        return 0
    srate = get_s32(fimap, offset+0x2A)
    if srate  < 8000 or srate > 64000:
        return 0
    return size + 0x40

def smlt_test(fimap, file_size, offset):
    HDR_LIST = (b'SMSB',b'SMPB',b'SOSB',b'SFPB',b'SFOB',b'SFPW',b'SMDB',b'SPSR')

    sub_hdr = get_b32(fimap, offset+0x20)
    if sub_hdr not in HDR_LIST:
        return 0

    nhdr = get_u8(fimap, offset+0x08) #number of banks
    mltsize = 0x20 * (nhdr + 1)

    temp_offset = offset + 0x20
    for _i in range(nhdr):
        hdr  = get_b32(fimap, temp_offset+0x00)
        bank = get_u8 (fimap, temp_offset+0x04)
        addr = get_s32(fimap, temp_offset+0x10)
        size = get_s32(fimap, temp_offset+0x14)

        if (addr >= 0 and get_b32(fimap, offset+addr) == hdr) or hdr == b'SFPW' or hdr == b'SPSR':
            totalsize = addr + size
            if totalsize > mltsize:
                mltsize = totalsize
        temp_offset += 0x20
        
    if mltsize > file_size:
        return 0
    return mltsize
    
def sdrv_test(fimap, file_size, offset):
    sub_hdr = get_b32(fimap, offset+0x50)
    if sub_hdr != b'2000':
        return 0
    size = get_s32(fimap, offset+0x08)
    if size > file_size:
        return 0
    return size

def misc_test(fimap, file_size, offset):
    version = get_u8(fimap, offset+0x04)
    size = get_s32(fimap, offset+0x08)
    
    if size > file_size or size > 0x800000 or version > 0x10: # Warning! May generate false positives!
        return 0
    return size

def get_hdrext(hdr):
    if sys.version_info.major == 2: #?
        return hdr[1:]
    else:
        return hdr[1:].decode('utf-8')
    
def dsf_search(fimap, file_size, basename, outdir):
    hdrmap = { b'SMLT': 0, b'SDRV': 0, b'SMSB': 0, b'SMPB': 0, b'SOSB': 0, b'SFPB': 0, b'SFOB': 0, b'SMDB': 0, b'SPSD': 0 }
    crcs_done = {}
    offset = 0

    while offset < file_size - 0x04:
        hdr = get_b32(fimap, offset+0x00)
        if hdr not in hdrmap:
            offset += 0x04
            continue


        size = 0x00
        if hdr == b'SPSD':
            size = spsd_test(fimap, file_size, offset)

        elif hdr == b'SMLT':
            size = smlt_test(fimap, file_size, offset)

        elif hdr == b'SDRV':
            size = sdrv_test(fimap, file_size, offset)

        else:
            size = misc_test(fimap, file_size, offset)
            #if not size:
            #    print("warning, unknown %s at %x" % (hdr, offset))

        if not size:
            offset += 0x04
            continue

        data = fimap[offset : offset + size]
        crc32 = binascii.crc32(data) 
        if crc32 in crcs_done:
            print('[0x%08X] ignored %s, 0x%x bytes' % (offset, hdr, size))
            offset += size
            continue
        crcs_done[crc32] = True

        ext = get_hdrext(hdr)
        if hdr == b'SPSD':
            ext = 'spsd'
        if hdr == b'SDRV':
            if hdrmap[hdr] == 0:
                foname = 'MANATEE.DRV'
            else:
                foname = 'MANATEE_%02d.%s' % (hdrmap[hdr], ext)
        else:
            foname = '%s_%03d.%s' % (basename, hdrmap[hdr], ext)
        print('[0x%08X] %s, 0x%x bytes' % (offset, foname, size))

        path_foname = os.path.join(outdir, foname)
        with open(path_foname,'wb') as fo:
            fo.write(data)

        hdrmap[hdr] += 1
        offset += size

    return hdrmap

#=====================================================================================================

def dsf_ext(finame, outdir):
    with open(finame,'rb') as fi:
        fimap = None
        try:
            file_size = os.path.getsize(finame)
            fimap = mmap.mmap(fi.fileno(), file_size, access=mmap.ACCESS_READ)
            if fimap[0:4] == b'\x00\xFF\xFF\xFF':
                raise ValueError("BIN mode not suported (convert to ISO first)")
        
            fibase = os.path.basename(finame)
            finoext, _ = os.path.splitext(fibase)
            finoext2, ext2 = os.path.splitext(finoext)
            if ext2: #double ext
                finoext = finoext2

            #done_ = mlt_search(fimap, file_size, finoext, outdir)
            done = dsf_search(fimap, file_size, finoext, outdir)

            totals = 0
            for item in done:
                if done[item]:
                    totals += done[item]
            if not totals:
                print('no files found (if this is a Naomi game, try decrypting first)')
            else:
                print('done: %s files' % (totals))

        finally:
            if fimap: fimap.close()
            fi.close()

def main(args):
    files = []
    for file_glob in args.files:
        files += glob.glob(file_glob)

    if not files:
        print("no files found")
        return

    for filename in files:
        curr_outdir = args.outdir
        if not curr_outdir:
            curr_outdir, _ = os.path.splitext(filename)
            curr_outdir2, ext2 = os.path.splitext(curr_outdir)
            if ext2: #double ext
                curr_outdir = curr_outdir2

        if not os.path.exists(curr_outdir):
            os.mkdir(curr_outdir)

        try:
            dsf_ext(filename, curr_outdir)
        except Exception as e:
            print("error processing %s: %s" % (filename, e))


def parse_args():
    description = (
        "Extracts data from Dreamcast/Naomi games"
    )
    epilog = (
        "examples:\n"
        "  %(prog)s (file.iso)\n"
        "  - extracts data from ISO\n"
    )

    ap = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", help="files to match", nargs='*', default=["*.BIN","*.DAT"])
    ap.add_argument("-o","--outdir", help="output dir (default: auto)", default=None)

    args = ap.parse_args()
    return args

if __name__ == '__main__':
    args = parse_args()
    main(args)
