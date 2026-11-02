# moves matched files to a subfolder
#
# 'mover.py **/*.ext' will move './blah/name.ext' to '_files/blah/name.ext'
# 
# 'mover.py' without parameters reads lines in '_files.txt' (wildcards or exact files) and moves them

import argparse, glob, os, shutil

DEFAULT_DIR = "_files"
TEXT_FILES = "_files.txt"

def move_files(args):
    matched_files = []

    if args.files == TEXT_FILES:
        if not os.path.isfile(TEXT_FILES):
            print(f"must pass files to move or {TEXT_FILES}")
            return
        with open(TEXT_FILES, "r", encoding="utf-8") as f:
            for line in f:
                entry = line.strip()
                if entry and not entry.startswith("#"):
                    matched_files.extend(glob.glob(entry, recursive=True))
    else:
        matched_files = glob.glob(args.files, recursive=True)

    destination_root = os.path.abspath(args.dir)
    files = []
    for f in matched_files:
        full_path = os.path.abspath(f)
        if os.path.isfile(full_path) and not full_path.startswith(destination_root):
            files.append(f)

    if not files:
        print("no files matched")
        return

    os.makedirs(args.dir, exist_ok=True)

    if args.verbose:
        print(f"moving {len(files)} files")

    for file in files:
        if args.flatten_dirs:
            target_path = os.path.join(args.dir, os.path.basename(file))
        else:
            relative_path = os.path.relpath(file, os.getcwd())
            target_path = os.path.join(args.dir, relative_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

        if args.verbose:
            print(f"moving: {file} to {target_path}")

        if not args.test:
            shutil.move(file, target_path)

            if not args.keep:
                source_dir = os.path.dirname(file)
                while source_dir and source_dir != os.getcwd():
                    if not os.listdir(source_dir):
                        os.rmdir(source_dir)
                        source_dir = os.path.dirname(source_dir)
                    else:
                        break

    print(f"moved {len(files)} files")

def main():
    parser = argparse.ArgumentParser(description="move files matching a glob pattern or listed in a file")
    parser.add_argument("files", nargs="?", default=TEXT_FILES, help=f"glob pattern or file list (default: {TEXT_FILES})")
    parser.add_argument("-d", "--dir", default=DEFAULT_DIR, help=f"destination directory (default: {DEFAULT_DIR})")
    parser.add_argument("-fd", "--flatten-dirs", action="store_true", help="flatten directory structure")
    parser.add_argument("-v", "--verbose", action="store_true", help="print verbose output")
    parser.add_argument("-t", "--test", action="store_true", help="simulate moves without executing them")
    parser.add_argument("-k", "--keep", action="store_true", help="keep source folders even if empty")

    args = parser.parse_args()
    move_files(args)

if __name__ == "__main__":
    main()
