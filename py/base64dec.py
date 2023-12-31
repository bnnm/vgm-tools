import base64, glob

files = glob.glob('*.b64')
for file in files:
    with open(file, 'rb') as f:
        data = base64.b64decode(f.read())
        
    with open(file + '.txt', 'wb') as f:
        f.write(data)
    