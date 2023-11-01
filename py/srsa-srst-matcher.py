# matches srsa and srst by comparing stream ids and created .txtm so vgmstream can match them

import glob, struct, os

ID_STREAM = 0x15F4D409
ID_SOUND = 0x70CBCCC5
#ID_CUE = 0x368C88BD
TARGETS_SRST = [ID_STREAM]
TARGETS_SRSA = [ID_SOUND]

FULL_MATCH = True
DEBUG_IDS = False

# renames .srsa to match .srst (not recommended since in rare cases .srsa are repeated = clashes)
RENAME_FILES = False
RENAME_SRSA = True #true = renames .srsa to match .srst, false = .srst to .srsa
RENAME_DEBUG = True

def find_ids(file, target_ids, data):
    pos = 0x00

    is_sr = False
    chunk_id = data[pos:pos+4]
    if chunk_id == b'ASRS' or chunk_id == b'TSRS':
        pos += 0x10
        is_sr = True

    chunk_id = data[pos:pos+4]
    if chunk_id != b'KTSR':
        print("ignored %s (expected KTSR, found %s)" % (file, chunk_id))
        return
    pos += 0x40

    ids = set()
    while pos < len(data):
        #print("%x" % pos)

        if pos + 0x0c >= len(data): #padding?
            break

        # base header
        chunk_id, chunk_size, stream_id = struct.unpack_from('<III', data, pos)
        if not chunk_id: #padding?
            break
        if not chunk_size:
            #found buggy file in FE Three Houses
            print("wrong file %s at %x" % (file, pos))
            break
        
        if chunk_id not in target_ids:
            pos += chunk_size
            continue


        include = False

        if chunk_id == ID_STREAM:
            stream_offset, stream_size = struct.unpack_from('<II', data, pos + 0x0c)
            stream_offset += pos
            include = True

        if chunk_id == ID_SOUND:
            flags, unk, head_offset, name_offset = struct.unpack_from('<IIII', data, pos + 0x0c)
            if (flags & 0x00010000):
                head_offset, unk = struct.unpack_from('<II', data, pos + head_offset) #offset to offset
                stream_offset, stream_size = struct.unpack_from('<II', data, pos + head_offset + 0x34)

                if is_sr:
                    stream_offset += 0x10 #SRST head

                include = True

        if include:
            if FULL_MATCH:
                # in some cases same ID can exists in different files, with different values
                key = (stream_id, stream_offset, stream_size)
            else:
                key = stream_id
            ids.add(key)

        pos += chunk_size

    return ids

def parse_files(files, targets):
    items = {}
    for file in glob.glob(files, recursive=True):
        with open(file, 'rb') as f:
            data = f.read()
        ids = find_ids(file, targets, data)
        if ids:
            items[file] = ids

        if DEBUG_IDS:
            temp_ids = list(ids)
            temp_ids.sort()
            print(file, temp_ids)

    return items

def main(is_sr=True):

    files_st = '*.srst'
    files_as = '*.srsa'
    if not is_sr:
        files_st = '*.ktsl2stbin'
        files_as = '*.ktsl2asbin'

    print('parsing st files: %s' % files_st)
    srsts = parse_files(files_st, TARGETS_SRST)
    print('parsing as files: %s' % files_as)
    srsas = parse_files(files_as, TARGETS_SRSA)

    not_found = []
    done = set()
    results = []

    #TODO improve
    print('matching results')
    for srsa in srsas:
        srsa_ids = srsas[srsa]
        found = False

        for srst in srsts:
            srst_ids = srsts[srst]
            if srsa_ids != srst_ids:
                continue

            #print('match', srst, srsa)
            base_srsa, _ = os.path.splitext(srsa)
            base_srst, _ = os.path.splitext(srst)
            if base_srsa == base_srst:
                continue

            if RENAME_FILES:
                if RENAME_SRSA:
                    ren_srsa = base_srst + '.srsa'
                    results.append("ren %s %s" % (srsa, ren_srsa))
                    if RENAME_DEBUG:
                        print(srsa, ren_srsa)                
                    else:
                        try:
                            os.rename(srsa, ren_srsa)
                        except:
                            print("can't rename %s to %s", srsa, ren_srsa)
                else:
                    ren_srst = base_srsa + '.srst'
                    results.append("ren %s %s" % (srst, ren_srst))
                    if RENAME_DEBUG:
                        print(srst, ren_srst)
                    else:
                        try:
                            os.rename(srst, ren_srst)
                        except:
                            print("can't rename %s to %s", srst, ren_srst)
            else:
                # TODO: handle subdirs (srst in subdir would be ok)
                clean_srsa = os.path.basename(srsa)
                clean_srst = os.path.basename(srst)
                line = "%s: %s" % (clean_srsa, clean_srst)
                if line not in done:
                    results.append(line)
                    done.add(line)
                found = True
        
        # in rare cases some ids seem to point to a wrong place leaving the original unused
        if not found:
            clean_srsa = os.path.basename(srsa)
            not_found.append('# %s' % (clean_srsa))

    if RENAME_FILES:
        with open('renames.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
    else:
        with open('.txtm', 'w', encoding='utf-8') as f:
            f.write('\n'.join(results))
            if not_found:
                f.write('\n'.join(['', '# not found:']))
                f.write('\n'.join(not_found))

main(is_sr=True)
