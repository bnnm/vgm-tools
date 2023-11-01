# generates download urls from ablist.json

import os, urllib.request, subprocess, json, hashlib

OUTPUT = 'urls.txt'
ABLIST = 'ablist.json'
ABLISTDEC = 'ablist.json.dec'
with open('current-url.txt', 'r') as f:
    CURRENT_URL = f.readline().strip()


def call(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def retrieve_ablist():
    if os.path.isfile(ABLISTDEC):
        return
    url = CURRENT_URL + ABLIST
    file = ABLIST
    urllib.request.urlretrieve(url, file)

    call(['biumdec.exe', file, file])

def parse_ablist():
    with open(ABLISTDEC, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    lines = [
        'out: bium-dl',
        'prefix: %s' % CURRENT_URL,
        'cut: %s' % CURRENT_URL,
        '#filter: albumdatatable, backtrack/*, mpmusicdata/*, musicdatatable, preview/*, systemsound, systemsoundse'
        '',
        '',
    ]

    # each url is in the form of (base-url)/(first-letter-of-hashname)/(hashname-of-bundlename)
    for asset in data["assetBundles"]:
        bn = asset["bundleName"]
        hash = hashlib.sha1()
        hash.update(bn.encode('utf-8'))
        bn_hash = hash.hexdigest().lower()

        subdir = bn_hash[0]
        url = f'{subdir}/{bn_hash} ` {bn}'
        lines.append(url)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

if __name__ == "__main__":
    retrieve_ablist()
    parse_ablist()
