# Makes urls from Nier Reincarnation and decrypts unity files if found.
# Needs database file (octocache*) from files/apk nearby, and current version for URLs.
#
# database and decryption from:
#   https://github.com/190nm/rein-kuro
# deps:
#   pip install protobuf
#   pip uninstall crypto
#   pip uninstall pycrypto
#   pip install pycryptodome
#   octodb_pb2.py (copy from rein-kuro)
#
# assets are saved into device like this:
# - get database from ? (has asset list and current url)
#   possibly downloaded encrypted + zipped, unzipped, re-crypted
#   - https://web.app.nierreincarnation.jp/assets/release/prd/20230218081004/database.bin.e
# - save as octocacheevai
#  /data/data/com.square_enix.android_googleplay.nierspjp/files/octo/pdb/201/300558242/octocacheevai
# - for each asset download using current url (see below)
# - calc MD5 from downloaded asset (2fc330cd133188dc07845b381ec0a350)
#   - this is in the database, but it's always calc'd
# - add A to asset name ("AZ8i4u5") and convert to hex > 415A3869347535
# - file is saved into base folder + ? (first number of hex?) + asset hex + md5
#   /data/data/com.square_enix.android_googleplay.nierspjp/files/octo/v1/201/5/415A3869347535/2fc330cd133188dc07845b381ec0a350
# - unity assets are decrypted based on database and real name
#
# How current version is made is unknown, but database is saved into a dir derived from version:
#  "300558242" dir > "200558242" version (so far that's the only version used).


import os, hashlib, json, glob
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# pre-generated db reader from google protocol buffer crap
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python" # slow but broken 4.x otherwise
import octodb_pb2

###

DB_NAME = 'octocacheevai'
URL_VERSION = '200558242'
DB_DUMP = False
URL_FILTER = ['audio)', 'mv', 'mm'] #'audio)bgm)', 'voice)' , 'tag.txt'
DECRYPT_OVERWRITE = True

###

def decrypt_db_kv(key, iv):
    key = bytes(key, "utf-8")
    key = hashlib.md5(key).digest()
    iv = bytes(iv, "utf-8")
    iv = hashlib.md5(iv).digest()
    cipher = AES.new(key, AES.MODE_CBC, IV=iv)

    with open(DB_NAME, 'rb') as f:
        data = f.read()

    if len(data) % 0x10 != 0:
        data = data[1:] #first byte = version? (0x01)
    data = cipher.decrypt(data)
    data = unpad(padded_data=data, block_size=16, style="pkcs7")

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
    keys = [
        ("p4nohhrnijynw45m", "LvAUtf+tnz", 'jp'),
        ("st4q3c7p1ibgwdhm", "LvAUtf+tnz", 'en'),
        ("ezj749zwskuskg46", "LvAUtf+tnz", 'jpcbt'), #jp beta?
        ("p4nohhrnijynw45m", "LvAUtf+tnz", 'encbt'), #en beta?
    ]
    data = None
    for key, iv, type in keys:
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

def generate_urls(db):
    # https://resources.app.nierreincarnation.jp/mama-{v}-{type}/{o}?generation={g}&alt=media
    
    pos = db.urlFormat.rindex('/') + 1
    url_base = db.urlFormat[0: pos] # {v}=version, {type}=asset?
    url_sub = db.urlFormat[pos:] #{o}=asset shortname, {g}=generation value
  
    lines = [
        'out: niin',
    ]

    url_bundles = url_base.replace('{v}', URL_VERSION).replace('{type}', 'assetbundle')
    url_resources = url_base.replace('{v}', URL_VERSION).replace('{type}', 'resources')
    
    lines += [
        '',
        'cut: -assetbundle/',
        f'prefix: {url_bundles}',
        '',
    ]
    # standard assets
    for item in db.assetBundleList:
        if URL_FILTER and not item.name.startswith(tuple(URL_FILTER)):
            continue
        
        url = url_sub.replace('{o}', item.objectName).replace('{g}', str(item.generation))
        url += ' ` %s'  % (item.name.replace(')','/'))
        lines.append(url)

    lines += [
        '',
        'cut: -resources/',
        f'prefix: {url_resources}',
        '',
    ]
    # plain resources
    for item in db.resourceList:
        if URL_FILTER and not item.name.startswith(tuple(URL_FILTER)):
            continue

        url = url_sub.replace('{o}', item.objectName).replace('{g}', str(item.generation))
        url += ' ` %s'  % (item.name.replace(')','/'))
        lines.append(url)

    outname = 'url-niin.txt'
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
