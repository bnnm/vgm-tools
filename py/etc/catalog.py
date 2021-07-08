# url dumper for catalog.json in apk
import json, os

# replaces
base_url = 'https://{Unity-parameter-to-remove}/'
out_url = 'https://(real-url-to-use-as-prefix)/'

with open('catalog.json', 'r', encoding='utf-8') as fi, open('url-gcr.txt', 'w') as fo:
    data = json.load(fi)
    
    fo.write('out: gcr\n')
    fo.write('cut: Android/\n')
    #fo.write('header: X-Verification-Code=XXXXXX\n')
    fo.write('filter: *_acb*, *_awb*, *_movie\n')
    fo.write('prefix: %s\n' % (out_url))
    fo.write('\n')

    assets = data['m_InternalIds']
    for asset in assets:
        if not asset.startswith('http'):
            continue
        url = asset.replace(base_url, '')
        fo.write('%s\n' % (url))
