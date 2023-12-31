# extracts raw data from .json
import json, glob


for file in glob.glob('*.json'):
    with open(file, 'rb') as f:
        jsondata = json.load(f)

    data = bytearray(jsondata['RawData'])

    outname = jsondata['m_Name']
    if data[0:4] == b'BKHD':
        outname += '.bnk'
    elif data[0:4] == b'RIFF':
        outname += '.wem'
    else:
        outname += '.bin'
    
    with open(outname, 'wb') as fw:
        fw.write(data)
