# decrypts a encrypted @UTF table (as seen in CPK headers)
import sys

START = 0x0
MAX = 0x10000

def decrypt_data(data, start, max, seed, incr):
    key = seed
    for i in range (start, start + max):
        data[i] = data[i] ^ key
        key = (key * incr) & 0xFF

def get_key(data, start):
    signature = b'@UTF'

    for seed in range(0, 255):
        if seed ^ data[start+0] != signature[0]:
            continue
        
        for increment in range(0, 255):
            tmp = seed
            #print("%i %i %x" % (seed, increment, tmp))

            tmp = (tmp * increment) & 0xFF
            if tmp ^ data[start+1] != signature[1]:
                continue

            tmp = (tmp * increment) & 0xFF
            if tmp ^ data[start+2] != signature[2]:
                continue

            tmp = (tmp * increment) & 0xFF
            if tmp ^ data[start+3] != signature[3]:
                continue

            return (seed, increment)
    return None

#            if ((encryptedUtfSignature[j] ^ m) != SIGNATURE_BYTES[j])
#            {
#                break;
#            }
#            else if (j == (SIGNATURE_BYTES.Length - 1))
#            {
#                keys.Add(LCG_SEED_KEY, seed);
#                keys.Add(LCG_INCREMENT_KEY, increment);
#                keysFound = true;
#            }

#for (byte seed = 0; seed <= byte.MaxValue; seed++)
#{
#    if (keysFound)
#        break
#
#    // match first char
#    if ((encryptedUtfSignature[0] ^ seed) != SIGNATURE_BYTES[0])
#        continue
#
#    for (byte increment = 0; increment <= byte.MaxValue; increment++)
#    {
#        if (!keysFound)
#            break
#
#        m = (byte)(seed * increment);
#
#        if ((encryptedUtfSignature[1] ^ m) != SIGNATURE_BYTES[1])
#              continue
#        t = increment;
#
#        for (int j = 2; j < SIGNATURE_BYTES.Length; j++)
#        {
#            m *= t;
#
#            if ((encryptedUtfSignature[j] ^ m) != SIGNATURE_BYTES[j])
#            {
#                break;
#            }
#            else if (j == (SIGNATURE_BYTES.Length - 1))
#            {
#                keys.Add(LCG_SEED_KEY, seed);
#                keys.Add(LCG_INCREMENT_KEY, increment);
#                keysFound = true;
#            }

#        } // if ((encryptedUtfSignature[1] ^ m) == SIGNATURE_BYTES[1])
#}
#

def main():
    if len(sys.argv) <= 1:
        print("missing filename")
        return
    file = sys.argv[1]

    with open(file, 'rb') as f:
        data = f.read()

    for i in range(START, START + MAX):
        key = get_key(data, i)
        if not key:
            continue
        print("key found at %x" % (i))


    key = get_key(data, START)
    if not key:
        print("unknown decryption/key")
        return
    seed, incr = key

    data = bytearray(data)
    decrypt_data(data, START, MAX, seed, incr)

    with open(file + '.dec', 'wb') as f:
        f.write(data)

main()
