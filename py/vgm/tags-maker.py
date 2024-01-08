# writes an empty tags.m3u file

import os, argparse


class TagsMaker(object):
    FILENAME_OUT = '!tags.m3u'
    EXCLUDED_EXTS = ['.py','.txt','.exe','.dll', '.bat', '.sh', '.m3u', '.7z', '.zip', '.rar']

    def __init__(self):
        self._args = None

        self._files = []


    def _parse(self):
        description = (
            "tags.m3u maker"
        )
        epilog = (
            "Creates a semi-empty !tags.m3u file\n"
            "Examples:\n"
            "  %(prog)s\n"
        )

        parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('-a',  '--tag-artist',   help="Add %%ARTIST tag per file")
        parser.add_argument('-T',  '--notag-title',  help="Don't add %%TITLE tag per file", action='store_true')
        return parser.parse_args()


    def _process(self):
        paths = os.listdir()
        paths.sort() #just in case

        for path in paths:
            if not os.path.isfile(path):
                continue

            name = os.path.basename(path) 
            if name.startswith('.'):
                continue

            __, extension = os.path.splitext(name)
            if extension in self.EXCLUDED_EXTS:
                continue

            self._files.append(name)


    def _write(self):
        with open(self.FILENAME_OUT, 'w', newline="\r\n") as outfile:
            outfile.write("# @ALBUM    \n")
            if not self._args.tag_artist:
                outfile.write("# @ARTIST   \n")
            outfile.write("# $AUTOTRACK\n")
            outfile.write("\n")

            for file in self._files:
                if self._args.tag_artist is not None: #allow empty
                    if self._args.tag_artist.strip():
                        outfile.write("# %%ARTIST   %s\n" % (self._args.tag_artist))
                    else:
                        outfile.write("# %ARTIST   \n")

                if not self._args.notag_title:
                    outfile.write("# %TITLE    \n")

                outfile.write('%s\n' % (file))

        print("done")


    def start(self):
        self._args = self._parse()
        self._process()
        self._write()


# #####################################

if __name__ == "__main__":
    TagsMaker().start()
