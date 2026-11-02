import os
import shutil

def read_cacheid_sourceid(path):
    pairs = []
    with open(path, 'r') as f:
        for line in f:
            if ':' in line:
                cacheid, sourceid = line.strip().split(':')
                cacheid = cacheid.strip()
                sourceid = sourceid.strip()
                pairs.append((cacheid, sourceid))
    return pairs

def read_filename_cacheid(path):
    mapping = {}
    with open(path, 'r') as f:
        for line in f:
            if ':' in line:
                filename, cacheid = line.strip().split(':')
                filename = filename.strip()
                cacheid = cacheid.strip()
                mapping[filename] = cacheid
    return mapping

def process_files():
    cacheid_sourceid = read_cacheid_sourceid('cacheid-sourceid.txt')
    filename_cacheid = read_filename_cacheid('filename-cacheid.txt')
    used = set()

    if not os.path.exists('memory'):
        os.makedirs('memory')

    for filename, cacheid in filename_cacheid.items():
        if not os.path.exists(filename):
            print(f"Skipping missing file: {filename}")
            continue

        sourceid = None
        for i, (cid, sid) in enumerate(cacheid_sourceid):
            if cid == cacheid and i not in used:
                sourceid = sid
                used.add(i)
                break

        if sourceid is None:
            print(f"No unused sourceID found for {filename} with cacheID {cacheid}")
            continue
        
        dirname = os.path.dirname(filename)
        new_name = f"{sourceid}.wem"
        new_name = os.path.join(dirname, new_name)

        if os.path.exists(new_name):
            existing_size = os.path.getsize(new_name)
            current_size = os.path.getsize(filename)
            move_target = os.path.join('memory', new_name)

            if existing_size < current_size:
                #print(f"Moving existing {new_name} to memory/ (smaller)")
                shutil.move(new_name, move_target)
            else:
                #print(f"Moving current {filename} to memory/ (smaller)")
                shutil.move(filename, move_target)
                continue  # skip renaming since original was moved
        try:
            os.rename(filename, new_name)
            #print(f"Renamed {filename} to {new_name}")
        except Exception as e:
            print(f"Error renaming {filename}: {e}")

if __name__ == "__main__":
    process_files()
