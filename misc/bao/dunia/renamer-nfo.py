import os
import xml.etree.ElementTree as ET
import argparse

def rename_files(nfo_path):
    # Derive base name and corresponding extract folder
    base_name = os.path.splitext(os.path.basename(nfo_path))[0]
    extract_dir = f"{base_name}.fat_extract"

    # Parse XML
    tree = ET.parse(nfo_path)
    root = tree.getroot()

    for file_elem in root.findall('File'):
        crc_hex = file_elem.get('CrcHex')
        target_path = file_elem.get('Path')

        # Normalize paths for cross-platform compatibility
        target_path = target_path.replace('\\', os.sep)
        target_full_path = os.path.join(extract_dir, target_path)

        # Source file based on CrcHex
        source_filename = crc_hex.lower().replace("0x", "")
        source_path = os.path.join(extract_dir, source_filename)

        if os.path.exists(source_path):
            os.makedirs(os.path.dirname(target_full_path), exist_ok=True)
            os.rename(source_path, target_full_path)
            #print(f"Renamed: {source_filename} → {target_path}")
        else:
            print(f"Missing: {source_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename FAT extract files based on .nfo XML metadata.")
    parser.add_argument("nfo_file", help="Path to the .nfo XML file")
    args = parser.parse_args()

    rename_files(args.nfo_file)
