import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

def extract_ids(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error reading XML file: {e}")
        return

    cache_to_source = defaultdict(set)
    output_lines = []

    # note that UE can set StreamType=bnk but memory .wem be a separate file
    for obj in root.iter('obj'):
        if obj.attrib.get('na') == 'AkMediaInformation':
            source_id = None
            cache_id = None

            for fld in obj.findall('fld'):
                if fld.attrib.get('na') == 'sourceID':
                    source_id = fld.attrib.get('va')
                elif fld.attrib.get('na') == 'cacheID':
                    cache_id = fld.attrib.get('va')

            if source_id and cache_id:
                try:
                    cache_id_int = int(cache_id)
                    cache_id_hex = f"0x{cache_id_int:08x}"
                except ValueError:
                    print(f"Warning: Invalid cacheID '{cache_id}' (not an integer)")
                    continue

                if source_id not in cache_to_source[cache_id_hex] and cache_to_source[cache_id_hex]:
                    existing = ', '.join(cache_to_source[cache_id_hex])
                    print(f"Warning: cacheID {cache_id_hex} has multiple sourceIDs: {existing}, {source_id}")
                cache_to_source[cache_id_hex].add(source_id)

    for cache_id_hex, source_ids in cache_to_source.items():
        for source_id in source_ids:
            output_lines.append(f"{cache_id_hex}: {source_id}")

    output_file = 'cacheid-sourceid.txt'
    try:
        with open(output_file, 'w') as f:
            for line in output_lines:
                f.write(line + '\n')
        print(f"Output saved to {output_file}")
    except Exception as e:
        print(f"Error writing output file: {e}")

if __name__ == "__main__":
    xml_file = sys.argv[1] if len(sys.argv) > 1 else 'banks.xml'
    extract_ids(xml_file)
