# Tool to fill IDs in wwnames:
# - make a missing ID list with missing IDs
#   - should have lines like "# 3933301714"
# - add words.py reversed names, format "3933301714: banana"
# - run this tool (drag and drop)
#   - this will replace "# 3933301714" with "banana"
#   - if list has "### (name)" sections, sections are sorted too
# - output is "(name)-clean.txt", except if (name) is wwname-*.txt in which case will be replaced
# - if some name is wrong add "#ko" at the end ("ZZSXSBanana #ko")
#   - use this script and wrong name will be converted back to "# (hash number)"

import sys, re

FULL_CLEAN = True
CLEAN_ORDER = True
UPDATE_ORIGINAL = True
#FNV_FORMAT = re.compile(r"^[A-Za-z_][A-Za-z0-9\_]*$")
HDR_FORMAT1 = re.compile(r"^###.+\(langs/(.+)\.bnk\)")
HDR_FORMAT2 = re.compile(r"^###.+\((.+)\.bnk\)")

class RageHasher():
    lookup_table = bytearray([
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
        0x40, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
        0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x5B, 0x2F, 0x5D, 0x5E, 0x5F,
        0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
        0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
        0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F,
        0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F,
        0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
        0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
        0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
        0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
        0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF,
        0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF,
    ])


    def is_hashable(self, lowname):
        return True

    #def __init__(self):
    #    self._hashes = {}
        
    #def swap_endian(self, value):
    #    return ((value >> 24) & 0x000000ff) | \
    #           ((value <<  8) & 0x00ff0000) | \
    #           ((value >>  8) & 0x0000ff00) | \
    #           ((value << 24) & 0xff000000)

    def get(self, hash):
        return self._hashes.get(hash, '')

    def _add_hash(self, line):
        hash = self.ragehash(line)
        hash_awc = hash & 0x1FFFFFFF

        #print("%08x: %s" % (hash, line))
        self._hashes[hash] = line
        self._hashes[hash_awc] = line

        # to catch inverted ints in the reader
        hash = self.swap_endian(hash)
        hash_awc = self.swap_endian(hash_awc)

        self._hashes[hash] = b'*'+line
        self._hashes[hash_awc] = b'*'+line

    def _ragehash_sub(self, bstr, initial_hash):
        hash = initial_hash

        for i in range(len(bstr)):
            hash += self.lookup_table[bstr[i]]
            hash &= 0xFFFFFFFF
            hash += (hash << 10)
            hash &= 0xFFFFFFFF
            hash ^= (hash >> 6)
            hash &= 0xFFFFFFFF

        return hash

    def get_hash_sub(self, bstr, initial_hash=0):
        return self._ragehash_sub(bstr, initial_hash)

    def get_hash_end(self, initial_hash=0):
        hash = initial_hash

        hash += (hash << 3)
        hash &= 0xFFFFFFFF
        hash ^= (hash >> 11)
        hash &= 0xFFFFFFFF
        hash += (hash << 15)
        hash &= 0xFFFFFFFF
        return hash

    def get_hash(self, bstr, initial_hash=0):
        hash = self._ragehash_sub(bstr, initial_hash)

        hash += (hash << 3)
        hash &= 0xFFFFFFFF
        hash ^= (hash >> 11)
        hash &= 0xFFFFFFFF
        hash += (hash << 15)
        hash &= 0xFFFFFFFF

        return hash

    def get_hash_lw(self, bstr, initial_hash=0):
        return self.get_hash(bstr, initial_hash)

    def get_hash_nb(self, bstr, initial_hash=0):
        return self.get_hash(bstr, initial_hash)

RAGEHASH = RageHasher()


def get_ragehash(name):
    namebytes = bytes(name.lower(), 'UTF-8')
    hash = RAGEHASH.get_hash(namebytes, initial_hash=0)
    return hash

def get_solved(line):
    if ':' not in line:
        return None

    sid, hashname = line.split(':', 1)
    sid = sid.strip()
    hashname = hashname.strip()

    #if not sid.isdigit():
    #    return None
    #if not is_hashable(hashname):
    #    return None
    if not sid.startswith('0x') and not sid.startswith('0X'):
        return None
    return (sid, hashname)

# remove double \n
def clean_lines(clines):
    prev = '****'
    lines = []
    for line in clines:
        if not line and not prev:
            continue
        prev = line
        lines.append(line)

    return lines

def sorter(elem):
    pos = 0
    item = elem.lower()
    if not elem:
        pos = 10
    elif elem[0].isdigit():
        pos = 1
    elif elem[0] == '#':
        pos = 2
        item = None # don't change order vs original (sometimes follows dev order)
    return (pos, item)

def order_list(clines):
    if not CLEAN_ORDER:
        return clines

    lines = [] #final list
    
    section = None
    slines = [] #temp section list

    for line in clines:
        s_end = not line
        s_start = line.startswith('### ')

        if (s_end or s_start) and section:
            # section end
            if slines: #only if section has something
                slines.sort(key=sorter)
                lines.append(section)
                lines.extend(slines)
            section = None
            slines = []

        if s_start:
            # register section header
            section = line
            continue

        if section:
            # lines within section
            slines.append(line)
        else:
            # any other
            lines.append(line)

    # trailing section
    if section and slines:
        slines.sort(key=sorter)
        lines.append(section)
        lines.extend(slines)

    return lines



def fix_wwnames(inname):
    blines = []
    hashed = {}
    koed   = set()
    cases  = {}


    # first pass
    with open(inname, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip('\r')
            line = line.strip('\n')

            items = get_solved(line)
            if items:
                # register solved ids and ignore line
                sid, hashname = items
                if sid not in hashed:
                    hashed[sid] = []
                if hashname not in hashed[sid]:
                    hashed[sid].append(hashname)
            else:
                # register base lines as-is, except when fixing headers
                if line.startswith('### '):
                    bankname = ''

                    match = HDR_FORMAT1.match(line)
                    if not match:
                        match = HDR_FORMAT2.match(line)
                    if match:
                        bankname, = match.groups()

                    if bankname.isdigit():
                        sid = int(bankname)
                        hashnames = hashed.get(sid)
                        if hashnames:
                            line = line.replace('.bnk', '.bnk: %s' % hashnames[0])

                # use case as found in first line 
                # (so if BLAH is used in several points and changed once to Blah, other points use that too)
                if line.lower() in cases:
                    line = cases[line.lower()]
                else:
                    cases[line.lower()] = line
                blines.append(line)

                if not line.startswith('#'):
                    hashname = line.split('#')[0]
                    sid = get_ragehash(hashname)
                    if sid not in hashed:
                        hashed[sid] = []
                    if hashname not in hashed[sid]:
                        hashed[sid].append(hashname)


    ko_all = False
    section = False
    clines = []
    for bline in blines:
        if bline.startswith('### '):
            section = True

        if bline.startswith('#@ko-all'):
            ko_all = True
            continue
    
        if ko_all and bline and not bline.startswith('#'):
            hashnames = bline.split(' ')
            sid = get_ragehash(hashnames[0])
            if section:
                bline = "# %08x" % (sid)
            else:
                continue

        if bline and bline.startswith('#ko') and ':' in bline and FULL_CLEAN:
            _, hashname = bline.split(':')
            hashname = hashname.strip()
            sid = get_ragehash(hashname)
            koed.add(hashname.lower())
            if section:  # '#ko' on top get ignored
                bline = "# %08x" % (sid)
            else:
                continue

        if bline.endswith('#ko') and FULL_CLEAN:
            if bline.startswith('# '):
                fnv = bline.split(' ')[1]
                koed.add(fnv.strip())
                continue
            elif bline.startswith('#'):
                pass
            else:
                hashname = bline.split('#ko', 1)[0]
                hashname = hashname.strip()
                sid = get_ragehash(hashname)
                koed.add(hashname.lower())
                if section: # '#ko' on top get ignored
                    bline = "# %08x" % (sid)
                else:
                    continue

        # remove ko'ed lines from other places
        if bline.lower() in koed and FULL_CLEAN:
            sid = get_ragehash(bline)
            if section: # '#ko' on top get ignored
                bline = "# %08x" % (sid)
            else:
                continue


        if bline.startswith('# ') and ':' not in bline:
            sid = bline[2:].strip()
            if sid in hashed:
                hashnames = hashed[sid]
                for i, hashname in enumerate(hashnames):
                    if FULL_CLEAN:
                        bline = "%s" % (hashname)
                    else:
                        bline = "%s: %s" % (sid, hashname)
                    if i > 0:
                        bline += ' #alt'
                    clines.append(bline)
                continue

        clines.append(bline)


    clines = order_list(clines)
    clines = clean_lines(clines)
    outname = inname
    
    update = UPDATE_ORIGINAL and 'wwnames' in outname
    if not update:
        outname = outname.replace('.txt', '-clean.txt')
    with open(outname, 'w', encoding='utf-8') as f:
       f.write('\n'.join(clines))




def main():
    if len(sys.argv) < 2:
        print("name not found")
        return
        
    for i in range(1, len(sys.argv)):
        inname = sys.argv[i]
        fix_wwnames(inname)

if __name__ == "__main__":
    main()
