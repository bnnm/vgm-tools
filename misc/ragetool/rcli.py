

from datetime import datetime
import glob, argparse, glob, os
import rhasher, rreader, rrel, rawc, rgenerator


HASHES_FILE = 'rnames.txt'

class Cli(object):
    def __init__(self):
        self._parser = None

        self._generator = rgenerator.TxtpGenerator()

    def _parse_init(self):
        title = 'rage-tool'
        version = ''
        #if rversion.RAGETOOL_VERSION:
        #    version += " " + rversion.RAGETOOL_VERSION

        description = (
            "%s%s - RAGE .rel parser by bnnm" % (title, version)
        )

        epilog = (
            "examples:\n"
            "  %(prog)s -d game.dat325.rel\n"
            "  - dumps .rel info to game.dat325.rel.txt\n"
            "  %(prog)s -r *.rel *.awc -g\n"
            "  - generates TXTP files from .awc and .rel\n"
        )

        parser = argparse.ArgumentParser(prog="wwiser", description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)

        p = parser.add_argument_group('base options')
        p.add_argument('files',                         help="Files to get (wildcards work)", nargs='*')
        p.add_argument('-r',  '--recursive',            help="Recursve load", action='store_true')
        p.add_argument('-d',  '--dump',                 help="Dump .rel info", action='store_true')
        p.add_argument('-g',  '--txtp',                 help="Generate TXTP", action='store_true')
        p.add_argument('-sl', '--save-lst',             help="Clean rnames.txt and include missing hashnames", action='store_true')

        self._args = parser.parse_args()


    def _parse_hasher(self):
        try:
            self._hasher = rhasher.RageHasher()
            with open(HASHES_FILE, 'rb') as f:
                print('reading hashes')
                self._hasher.read_hashfile(f)
        except:
            print("no hashes found")


    def _is_filename_ok(self, filenames, filename):
        if not os.path.isfile(filename):
            return False
        if filename.upper() in (filename.upper() for filename in filenames):
            return False
        if filename.endswith(".py"):
            return False
        return True

    def _add_files(self, files, filenames):
        for file in files:
            if not self._is_filename_ok(filenames, file):
                continue
            filenames.append(file)

    def _get_filenames(self, args):
        filenames = []
        for file in args.files:
            # existing file: manually test as glob expands "[...]" inside paths
            if os.path.isfile(file):
                self._add_files([file], filenames)
                continue

            # wildcards: try globbed
            if args.recursive:
                if '**' not in file:
                    file = '**/' + file
                glob_files = glob.glob(file, recursive=True)
            else:
                glob_files = glob.glob(file)
            self._add_files(glob_files, filenames)
        return filenames

    def _parse_files(self):
        hasher = self._hasher

        print('reading files')

        filenames = self._get_filenames(self._args)
        for filename in filenames:
            print(f'reading {filename}')
            with open(filename, 'rb') as f:
                data = f.read()
            r = rreader.Reader(filename, data)

            if True:
                if data[0:4] == b'DATA' or data[0:4] == b'ADAT':
                    obj = rawc.AwcParser(r, hasher)
                    obj.parse()

                    self._generator.add_awc(obj)
                else:
                    obj = rrel.RelParser(r, hasher)
                    obj.parse()
                    self._generator.add_rel(obj)

            #except ValueError:
            #    print(f'ignored unsupported file {filename}')
            #    continue

            if self._args.dump:
                print(f"dumping {filename}")
                obj.save()
                #obj.print()

    def _save_names(self):
        if not self._args.save_lst:
            return
        hasher = self._hasher

        print('writting rnames')
        current_datetime = datetime.now()
        outname = 'rnames-%s.txt' % (current_datetime.strftime('%Y%m%d%H%M%S'))
        with open(outname, 'w') as f:
            f.write('\n'.join(hasher.get_registers()))

    def _generate(self):
        if not self._args.txtp:
            return
        self._generator.add_hasher(self._hasher)
        self._generator.start()

    def start(self):
        self._parse_init()
        self._parse_hasher()
        self._parse_files()
        self._save_names()
        self._generate()



def main():
    Cli().start()
