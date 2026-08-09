# Makes urls from 'octo' games + decrypts unity files in subdirs if found.
# Needs database file (octocache*) from files/apk nearby, and current version for URLs.
# Tested with: Nier Reincarnation, FF7 Ever Crisis
#
# deps:
#   pip install protobuf
#   pip uninstall crypto
#   pip uninstall pycrypto
#   pip install pycryptodome
#   octodb_pb2.py (copy from rein-kuro)
#
# database parsing and decryption derived from:
#   https://github.com/190nm/rein-kuro
# may be useful:
#   https://github.com/shalzuth/ff7ecapi
#   https://github.com/kishidanatsumi/gkmasToolkit/
#
# -----------------------------------------------------------------------------
# how to:
# - install game + run it to download database
#   - this is done via API, see https://github.com/shalzuth/ff7ecapi
# - get database file (needs rooted phone)
#   Nier: /data/data/com.square_enix.android_googleplay.nierspjp/files/octo/pdb/201/300558242/octocacheevai
#   FF7EC: /data/data/com.square_enix.android_googleplay.ff7ecjp/files/octo/pdb/3001/223173179/octocacheevai
# - find database key and add it to DB_KEYS below
#   - get global-metadata.dat + decrypt (xor_gm.py) if needed
#   - use Il2CppDumper w/ libil2cpp.so + global-metadata.dat, open stringliteral.json
#   - find lines that are 16-char long and try those (there are several candidates)
#   - keys seem to be letter (lowecase?) + numbers only: 
#     - value": "(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{16}"
#   - database IV seems fixed but it's also found in global-metadata
# - edit URL_VERSION and FILE_FILTER if needed
#   - Nier needed a version, while FF7EC doesn't
#     version location is unknown, but database is saved into a dir derived from it:
#     "300558242" dir > "200558242" version (only version used).
# - put octo.py + octodb_pb2.py + octocacheevai together
# - run octo.py, will generate url-octo.txt (filtered to FILE_FILTER)
#   - for other games you may want DECRYPT_OVERWRITE to debug octocacheevai contents after decryption
#     raw data is in octocacheevai.dump and translated database in octocacheevai.txt
#   - octodb_pb2.py may need to be tweaked per game (currently same for Nier and FF7EC)
# - check url-octo.txt and drag-and-drop to download with dl.py
# - run octo.py again to decrypt downloaded files if needed
#
# assets are saved into device like this:
# - get database from asset info (has asset list and current url)
#   possibly downloaded encrypted + zipped, unzipped, re-crypted
# - save as octocacheevai
# - for each asset download using current url (see below)
# - calc MD5 from downloaded asset (2fc330cd133188dc07845b381ec0a350)
#   - this is in the database, but it's always calc'd
# - add A to asset name ("AZ8i4u5") and convert to hex > 415A3869347535
# - file is saved into base folder + ? (first number of hex?) + asset hex + md5
#   /data/data/com.square_enix.android_googleplay.nierspjp/files/octo/v1/201/5/415A3869347535/2fc330cd133188dc07845b381ec0a350
# - unity assets are decrypted based on database and real name
#


import os, hashlib, json, glob
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# pre-generated db reader from google protocol buffer crap
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python" # slow but broken 4.x otherwise
import octodb_pb2

#---

URL_VERSION = '200558242'
#FILE_FILTER = ['audio)', 'mv', 'mm'] #Nier
FILE_FILTER = ['.acf', '.acb', '.awb', '.usm'] #FF7EC
DECRYPT_OVERWRITE = True

DB_NAME = 'octocacheevai'
DB_DUMP = False
DB_KEYS = [
    ("bqra7ocyyu7he9b5", "LvAUtf+tnz"), # FF7 Ever Crisis JP
    #("2heo6veklua365wl", "LvAUtf+tnz"), # FF7 Ever Crisis JP? (found in global-metadata.dat)
    #("LkFwaWIGcHJvdG8z", "LvAUtf+tnz"), # FF7 Ever Crisis JP? (found in global-metadata.dat)
    #("bnVtc2IGcHJvdG8z", "LvAUtf+tnz"), # FF7 Ever Crisis JP? (found in global-metadata.dat)
    #("dGl0eWIGcHJvdG8z", "LvAUtf+tnz"), # FF7 Ever Crisis JP? (found in global-metadata.dat)
    #("v14uh2c77pv8xkfe", "LvAUtf+tnz"), # FF7 Ever Crisis JP? (found in global-metadata.dat)
    #("2heo6veklua365wl", "LvAUtf+tnz"), # FF7 Ever Crisis JP? (found in global-metadata.dat)
    #("57lk6xzzeqmy4qay", "LvAUtf+tnz"), # FF7 Ever Crisis EN?
    #("1nuv9td1bw1udefk", "LvAUtf+tnz"), # Gakuen iDOLM@STER 'jp'?
    #("p4nohhrnijynw45m", "LvAUtf+tnz"), # Nier Reincarnation 'jp', 'encbt' en beta?
    #("st4q3c7p1ibgwdhm", "LvAUtf+tnz"), # Nier Reincarnation 'en'
    #("ezj749zwskuskg46", "LvAUtf+tnz"), # Nier Reincarnation 'jpcbt' jp beta?
    #("5osa257ifw2lczq4", "LvAUtf+tnz"), # Nier Reincarnation? (seen in global-metadata)
    #("l488k2zmalogay24", "LvAUtf+tnz"), # Nier Reincarnation? (seen in global-metadata)
]

#---

def decrypt_db_kv(base_key, base_iv):
    key = bytes(base_key, "utf-8")
    key = hashlib.md5(key).digest()
    iv = bytes(base_iv, "utf-8")
    iv = hashlib.md5(iv).digest()
    cipher = AES.new(key, AES.MODE_CBC, IV=iv)

    with open(DB_NAME, 'rb') as f:
        data = f.read()
    
    if len(data) % 0x10 != 0:
        data = data[1:] #first byte = version? (0x01)
    data = cipher.decrypt(data)
    data = unpad(padded_data=data, block_size=16, style="pkcs7")
    print("using key", base_key)
    if DB_DUMP:
        with open(DB_NAME + '.dump', 'wb') as f:
            f.write(data)

    data_md5 = data[0:16]
    data_main = data[16:]
    calc_md5 = hashlib.md5(data_main).digest()
    if data_md5 != calc_md5:
        raise ValueError("wrong md5")

    return data_main


def decrypt_db():
    data = None
    for key, iv in DB_KEYS:
        try:
            return decrypt_db_kv(key, iv)
        except ValueError as e:
            pass #wrong key
    raise ValueError("can't decrypt database")


def parse_db(data):
    db = octodb_pb2.Database()
    db.ParseFromString(data)

    if DB_DUMP:
        lines = []

        for item in db.assetBundleList:
            lines.append(str(item))
        
        for item in db.resourceList:
            lines.append(str(item))

        with open(DB_NAME + '.txt', 'w') as f:
            f.write('\n'.join(lines))

    return db


def generate_url_lines(db_items, file_filter, url_sub, base_url):
    urls = []
    for item in db_items:
        if file_filter and not any(x in item.name for x in file_filter):
            continue
        url = url_sub
        url = url.replace('{o}', item.objectName)
        url = url.replace('{g}', str(item.generation))
        url += ' ` %s'  % (item.name.replace(')','/'))
        urls.append(url)
    if not urls:
        return []
    urls.sort(key=lambda x: x.split("` ", 1)[1])

    lines = [
        '',
        #'cut: -assetbundle/',
        f'prefix: {base_url}',
        '',
    ]
    lines += urls
    return lines


def generate_urls(db):
    # transform partial urls in octocacheevai to final urls:
    # - Nier: https://resources.app.nierreincarnation.jp/mama-{v}-{type}/{o}?generation={g}&alt=media
    # - FF7EC: https://resources-data-u8hrp32d.app.jp.ffviiec.com/{o}
    # {v}=version
    # {type}=asset type
    # {o}=asset shortname
    # {g}=generation value
    
    pos = db.urlFormat.rindex('/') + 1
    url_base = db.urlFormat[0: pos]
    url_sub = db.urlFormat[pos:]
  
    lines = [
        'out: dl-octo',
    ]

    url_bundles = url_base.replace('{v}', URL_VERSION).replace('{type}', 'assetbundle')
    url_resources = url_base.replace('{v}', URL_VERSION).replace('{type}', 'resources')

    lines += generate_url_lines(db.assetBundleList, FILE_FILTER, url_sub, url_bundles)
    lines += generate_url_lines(db.resourceList, FILE_FILTER, url_sub, url_resources)

    outname = 'url-octo.txt'
    with open(outname,'w',encoding='utf-8') as f:
        f.write('\n'.join(lines))


def get_key(mask):
    mask_len = len(mask)
    key = bytearray(mask_len * 2)
    key_len = len(key)

    # setup base key
    ka = 0;
    kb = key_len - 1
    for i in range(mask_len):
        elem = mask[i]
        key[ka] =  elem
        key[kb] = (~elem) & 0xFF
        ka +=  2
        kb += -2

    # scramble key
    xor = 0xBB;
    for i in range(key_len):
        xor = ((xor & 1) << 7 | xor >> 1) & 0xFF # rotate right
        xor = key[i] ^ xor

    for i in range(key_len):
        key[i] ^= xor;

    return key


def decrypt_file(data, name):
    buffer = bytearray(data)
    input_len = len(buffer)
    #name_len = len(name)

    if buffer[0] == 0x31: #header only
        crypt_len = 0x100
    elif buffer[0] == 0x32: #full data
        crypt_len = input_len
    else: #not encrypted
        return None

    key = get_key(name.encode('utf-8'))
    key_len = len(key) #name_len * 2 #<< 1
    #print(key_len, key)

    for i in range(crypt_len):
        xor = key[i % key_len]
        buffer[i] ^= xor
    buffer[0] = 0x55; #manually overwritten with 0x55 ("UnityFS"'s "U")
    return buffer


def decrypt_files(db):
    files = []
    files += glob.glob('**/*', recursive=True)

    if not files:
        print("no files to decrypt")
        return

    # we need name to decrypt
    real_names = {}
    for item in db.assetBundleList:
        real_names[item.md5] = item.name
        real_names[item.objectName] = item.name
    for item in db.resourceList:
        real_names[item.md5] = item.name
        real_names[item.objectName] = item.name


    for file in files:
        if not os.path.isfile(file):
            continue
        # standard resources aren't encrypted
        _, ext = os.path.splitext(file)
        if ext:
            continue

        basename = os.path.basename(file)
        basename = os.path.splitext(basename)[0]

        with open(file, 'rb') as f:
            data = f.read()

        # find read name
        real_name = real_names.get(basename)
        if not real_name:
            md5 = hashlib.md5(data).hexdigest().lower()
            real_name = real_names.get(md5)

        if not real_name:
            continue
        #print(file, real_name)

        
        # decrypt and save
        data_dec = decrypt_file(data, real_name)
        if not data_dec: #not encrypted
            continue
        
        outname = file
        if not DECRYPT_OVERWRITE:
            outname += '.dec'
        with open(outname,'wb') as f:
            f.write(data_dec)

def main():
    print("decrypting db")
    data = decrypt_db()

    print("parsing db")
    db = parse_db(data)

    print(f"processing urls (db {db.revision})")
    generate_urls(db)

    print("decrypting files")
    decrypt_files(db)

    print("done")

main()
