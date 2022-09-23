import hashlib, sys, os

if len(sys.argv) <= 1:
    print("missing file list")
    exit()

# config
hashtype = 'md5'
files_list = sys.argv[1]
check_hash = True
lowercase = False
rename = True
#


def get_hash(text):
    if lowercase:
        text = text.lower()

    hash_bytes = text.encode('utf-8')
    return hashlib.md5(hash_bytes).hexdigest()

def main():
    with open(files_list, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            items = line.strip().split(" ", 1)
            if len(items) == 1:
                text = items[0]
                hash = get_hash(text)
            else:
                hash = items[0]
                text = items[1]

            if check_hash:
                hash_calc = get_hash(text)
                #hash_bytes  != (...).digest() ?

                if hash != hash_calc:
                    print("ignored wrong hash %s for %s (expected %s)" % (hash, text, hash_calc))
                    continue

            if rename:
                try:
                    basedir = os.path.dirname(text)
                    if basedir:
                        os.makedirs(basedir)
                except:
                    pass

                try:
                    os.rename(hash, text)
                except:
                    print("can't rename %s to %s" % (hash, text))

main()
