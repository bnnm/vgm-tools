# reimplementation of shiren6dec.cs b/c this is easier for me than .NET
# (although .NET version is easier to compare vs decompilations)

from Crypto.Cipher import AES
from Crypto.Util import Counter
from Crypto.Protocol import KDF
from Crypto.Hash import SHA1
import hashlib, glob, os

# semi-custom PBKDF1 (Rfc2898DeriveBytes is PBKDF2-HMAC-SHA-1)
#  KDF.PBKDF1(password, salt, length, count) seems to require 8-byte salt
#  https://github.com/microsoft/referencesource/blob/master/mscorlib/system/security/cryptography/passwordderivebytes.cs
#  https://stackoverflow.com/questions/27791726/encryption-diff-between-java-and-c-sharp/27798812#27798812
def MS_PasswordDeriveBytes(password, salt, key_size=16, iterations=100):
    # ComputeBaseValue
    hash = hashlib.sha1()
    hash.update(password)
    if salt:
        hash.update(salt)
    base_hash = hash.digest()

    for i in range(iterations - 1):
        base_hash = hashlib.sha1(base_hash).digest()
    out_hash = base_hash

    # ComputeBytes (not used when key_size=16)
    counter = 1
    while len(out_hash) < key_size:
        hash_counter = counter.to_bytes(4, byteorder='little')
        out_hash += hashlib.sha1(hash_counter + hash).digest()
        counter += 1
        print(counter, len(out_hash) < length)
    return out_hash[0: key_size]

# .NET AES CTR (as found in some games, not sure if standard)
# each block (starting from 1):
# - move counter to LE 0x10 array (block number 0x1122 = {0x22, 0x11, 0x00, 0x00})
# - encrypt array with AES-128-ECB
# - use resulting array to un-xor current 0x10 block
def decrypt_aes_ctr(data, key):
    ctr = Counter.new(128, little_endian=True, initial_value=1)
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.decrypt(data)


password = b'DtUp!43AZH46@*fj768GCM@ajNvEdBEB'
for file in glob.glob('*.bundle'):
    name = file
    name = os.path.basename(name)
    name = os.path.splitext(name)[0]
    
    salt = name.encode('utf-8')
    key = MS_PasswordDeriveBytes(password, salt)
    

    with open(file, 'rb') as f:
        data = f.read()

    data = decrypt_aes_ctr(data, key)
    with open(file + '.dec', 'wb') as f:
        f.write(data)
