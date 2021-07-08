# writes extensions without folders for fun

import os


items = []
for root, dirs, files in os.walk('.'):
    for file in files:
        if file == 'lister.py':
            continue
        path = os.path.join(root, file)
        if path.startswith('.\\'):
            path = path[2:]
        items.append(path)

items.append('')

with open('lister.txt', 'w', encoding='utf-8') as fo:
    fo.write('\n'.join(items))
