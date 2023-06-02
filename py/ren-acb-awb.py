# makes a .bat renamer from .acb+awb (put together first)
import glob, struct, os, hashlib

REN_LOWER = False


# CRI UTF has a certain structure but it's kinda complex so just fake it by looking by nearby strings
class CriRenamer():
    def __init__(self):
        self._acbs = [] #(filename, acbname, awbhash)
        self._awbs = {} #hash to filename


    def _get_awbhash(self, filename, data):
        find_target = b'StreamAwb\0Name\0Hash\0'

        pos = data.find(find_target)
        if pos < 0:
            return None
        pos += len(find_target)

        end = data.find(b'\x00', pos)
        if end < 0:
            return None
        end += 1
        return data[end:end+0x10]
    
    def _get_acbname(self, filename, data):
        find_target = b'Build:\n\0'

        pos = data.find(find_target)
        if pos < 0:
            print("warning: name not found in:", filename)
            return '?'
        pos += len(find_target)

        end = data.find(b'\x00', pos)
        if end < 0:
            print("warning: wrong end in:", filename)
            return '?'

        name = data[pos:end]
        if not name or name == b'\x00':
            print("warning: empty name in:", filename)
            return ''

        name = name.decode("utf-8") .strip()
        return name
    
    def _parse_acb(self, filename, data):
        acbname = self._get_acbname(filename, data)
        # could also find awb name but almost always it's the same as awb (in rare cases could be N awbs)
        awbhash = self._get_awbhash(filename, data)
        
        if data.find(b'ACB Format') > 0:
            ext = 'acb'
        elif data.find(b'ACF Format') > 0:
            ext = 'acf'
        else:
            ext = 'unk'
        
        elem = (filename, acbname, awbhash, ext)
        self._acbs.append(elem)
        pass

    def _parse_awb(self, filename, data):
        hash = hashlib.md5(data).digest()
        self._awbs[hash] = filename
        pass

    # include new file
    def parse_file(self, filename):
        with open(filename, 'rb') as f:
            data = f.read(0x04)

            if data == b'@UTF':
                data += f.read() 
                self._parse_acb(filename, data)
            elif data == b'AFS2':
                data += f.read()
                self._parse_awb(filename, data)
            else:
                return

    # save results (at the end after all files are loaded)
    def generate(self):
        renames = []
        for acb_filename, name, awbhash, ext in self._acbs:

            if True:
                acb_basename = os.path.basename(acb_filename)

                ren_name = '%s.%s' % (name, ext)
                if REN_LOWER:
                    ren_name = ren_name.lower()
                line = "ren %s %s" % (acb_basename, ren_name)
                if not name or name == '?' or acb_basename.lower() == ren_name.lower():
                    line = 'REM #' + line
                renames.append(line)

            awb_filename = self._awbs.get(awbhash)
            if awb_filename:
                awb_basename = os.path.basename(awb_filename)
                
                ren_name = '%s.awb' % name
                if REN_LOWER:
                    ren_name = ren_name.lower()
                line = "ren %s %s" % (awb_basename, ren_name)
                if not name or name == '?':
                    line = 'REM #' + line
                renames.append(line)

        with open("_ren_cri.bat", 'w', encoding='utf-8') as f:
            f.write('\n'.join(renames))


def main():
    cri = CriRenamer()

    filenames = glob.glob("*")
    
    items = []
    for filename in filenames:
        if not os.path.isfile(filename):
            continue
        cri.parse_file(filename)

    cri.generate()

main()