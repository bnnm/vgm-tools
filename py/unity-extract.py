# Quick unity asset extractor based on: https://github.com/K0lb3/UnityPy
# Extracts audio/video by default
# - install UnityPy: 
#   pip install UnityPy
#   (also )
# - extract:
#   unity-extract.py (files)

# TODO: detect exceptions write some !unity-errors.txt
# TODO: handle all types
# TODO: check https://github.com/K0lb3/UnityPy/blob/master/UnityPy/tools/extractor.py

import os, struct, argparse, glob
import UnityPy

EXTRACTED_ASSETS = ['AudioClip', 'TextAsset', 'VideoClip']

class ObjectHandler():
    def __init__(self, args, file, obj, dst_done, path=None):
        self.args = args
        self.file = file
        self.obj = obj
        self.path = path
        self.data = None
        self.mv = None
        self.dst_done = dst_done


    def update_ext(self):
        # could use UnityPy.enums.Audio.AUDIO_TYPE_EXTEMSION.get(data.m_CompressionFormat, ".audioclip")
        # but some audio are in text assets, and not sure how exact is m_CompressionFormat

        ID_EXTS = {
            b'@UTF': '.acb',
            b'AFS2': '.awb',
            b'FSB5': '.fsb',
            b'RIFF': '.wav',
            b'CRID': '.usm',
            b'OggS': '.ogg',
        }
        ID_EXTS2 = {
            b'ftyp': '.mp4',
        }
        
        base_dst, base_ext = os.path.splitext(self.dst)
        _, orig_ext = os.path.splitext(base_dst)

        mv = self.mv
        head_id = mv[0x00:0x04]
        head_id2 = mv[0x04:0x08]
        
        ext = ID_EXTS.get(head_id)
        if not ext:
            ext = ID_EXTS2.get(head_id2)
        if not ext:
            ext = '.bin'

        if head_id == b'@UTF' and b'ACF' in mv:
            ext = '.acf'
        if head_id == b'RIFF' and mv[0x08:0x0c] == b'FEV ':
            ext = '.bank'

        # detect correct extension
        # rarely there is an actual extension, but not always correct (.wav for .fsb)
        # examples:
        #   blah.bytes
        #   blah.acb #correct
        #   blah.acb.bytes #correct but double
        #   blah.wav #fsb5

        dst = base_dst
        if orig_ext and ext not in ['.fsb']:
            pass #dst already has extension and is valid
        
        elif base_ext and ext == '.bin':
            dst += base_ext # use existing ext

        else:
            dst += ext # use calc'd ext
        

        self.dst = dst


    def update_name(self):
        outdir = self.args.outdir
        if self.path:
            dst = os.path.join(outdir, *self.path.split("/"))
        else:
            try:
                name = self.data.name
            except:
                name = None #not all objects have one

            if not name: #object name can be empty too
                name = self.obj.type.name

            dst = os.path.join(outdir, name)
        self.dst = dst

    def is_asset_type_ok(self):
        return self.obj.type.name in EXTRACTED_ASSETS

    def check_dupe(self):
        dst = self.dst
        dst_done = self.dst_done

        if dst in dst_done:
            count = dst_done[dst]
            dst_done[dst] += 1

            dst, ext = os.path.splitext(dst)
            dst = "%s#%04i%s" % (dst, count, ext)
        else:
            dst_done[dst] = 1

        self.dst = dst

    def handle(self):
        obj = self.obj

        if self.args.list:
            try:
                self.data = obj.read()
                self.update_name()
                print(f'{self.dst} [{obj.type.name}]')
            except:
                print(f'unsupported object {obj.type.name} in {self.file}')

            return

        if not self.is_asset_type_ok():
            #print(f'skipping: {dst}')
            return

        # get actual Object
        data = obj.read()
        self.data = data
        
        intdata = None
        if obj.type.name == "AudioClip":
            # no other way to get actual clip data (API converts to wav)
            intdata = data.m_AudioData

        if obj.type.name == "TextAsset":
            intdata = data.script

        if obj.type.name == "VideoClip":
            intdata = data.m_VideoData

        if not intdata:
            print('data not found')
            return

        self.mv = memoryview(intdata)
        self.update_name()
        self.update_ext()

        dst = self.dst
        if not dst:
            dst = 'unknown.bin'
        self.check_dupe()

        data_bytes = self.mv #mv.tobytes()

        print(f'writting: {dst}')
        os.makedirs(os.path.dirname(dst), exist_ok = True)
        with open(dst, 'wb') as f:
            f.write(data_bytes)



def handle_file(args, file):
    env = UnityPy.load(file)
    DST_DONE = {}

    # reads Assets
    if not args.plain:
        for path, obj in env.container.items():
            hobj = ObjectHandler(args, file, obj, DST_DONE, path)
            hobj.handle()
    else:
        for obj in env.objects:
            hobj = ObjectHandler(args, file, obj, DST_DONE)
            hobj.handle()

    if not env.objects:
        print(f'ignored: {file} [not unity/encrypted?]')


def main_sub(args):
    IGNORED_EXTS = set(['.py', '.txt', '.fsb'])

    if args.key:
        UnityPy.set_assetbundle_decrypt_key(args.key)

    if args.version:
        UnityPy.config.FALLBACK_UNITY_VERSION = args.version
        UnityPy.AssetsManager.version_engine = args.version

    #if args.version_check:
    #    if UnityPy.__version__ != '1.x.x':
    #        raise ImportError("Invalid UnityPy version detected. Please use version 1.9.6")


    if True:
    #try:
        files = []
        for file_glob in args.files:
            files += glob.glob(file_glob, recursive=True)

        if not files:
            raise ValueError("no files found")
    
    
        for file in files:
            _, ext = os.path.splitext(file)
            if ext in IGNORED_EXTS:
                continue
            if os.path.isdir(file):
                continue
        
            if True:
            #try:
                handle_file(args, file)
            #except Exception as e:
            #    print("error processing %s: %s" % (file, e))

    #except Exception as e:
    #    print("error: %s" % (e))

def main(args):
    try:
        main_sub(args)
    except AttributeError as e:
        if 'version_engine' in str(e):
            print("version not found? (set manually)")
        else:
            raise e
    

def parse_args():
    description = (
        "Extract unity assets"
    )
    epilog = None

    ap = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("files", help="files to match", nargs='*', default=["*","**/*"])
    ap.add_argument("-l","--list", help="list assets only", action='store_true')
    ap.add_argument("-p","--plain", help="use plain paths instead of internal paths (if available)", action='store_true')
    ap.add_argument("-v","--version", help="set Unity version", default=None)
    ap.add_argument("-k","--key", help="set Unity CN key", default=None)
    ap.add_argument("-f","--filter-include", help="Include files that match wildcard filter", default=None)
    ap.add_argument("-F","--filter-exclude", help="Include files that don't match wildcard filter", default=None)
    ap.add_argument("-o","--outdir", help="output dir", default='out')

    args = ap.parse_args()
    return args

if __name__ == "__main__":
    args = parse_args()
    main(args)
