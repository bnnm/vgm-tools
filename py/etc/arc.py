# extracts from arcaea iirc

import json, os, sys

basedir = 'out/'
file = 'arc.bin'
if len(sys.argv) > 1:
    file = sys.argv[1]

with open('arc.json') as f:
    arc = json.load(f)

with open(file) as f:
    for group in arc['Groups']:
        for entry in group['OrderedEntries']:
            name = entry["OriginalFilename"]
            offset = entry["Offset"]
            size = entry["Length"]
            
            f.seek(offset)
            data = f.read(size)
            
            outname = basedir + name
            os.makedirs(os.path.dirname(outname), exist_ok=True)

            with open(outname, 'wb') as fo:
                fo.write(data)
