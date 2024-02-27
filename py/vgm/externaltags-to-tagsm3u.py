# writes !tags.m3u from externaltag's folder.tags

import os, argparse, struct
import collections


track_tags = {
    'TRACK',
    'TRACKNUMBER',
    'TOTALTRACKS',
}

def sorter(item):
    if not item:
        return

    _, _, tags = item
    disc = 0
    track = 0 #999?
    for tagname, tagvalue in tags:
        if tagname.upper() in ['DISC'] and tagvalue.isdigit():
            disc = int(tagvalue)

        if tagname.upper() in ['TRACKNUMBER', 'TRACK'] and tagvalue.isdigit():
            track = int(tagvalue)
    return (disc, track)

class ExtTagsMaker(object):
    FILENAME_IN = 'folder.tags'
    FILENAME_OUT = '!tags.m3u'

    def __init__(self):
        self._args = None

        self._files = []
        self._subsongs = {}
        self._globaltagsnames = {}
        self._globaltags = []
        self._skip_global = ['STREAM_NAME'] #never used as global

    def _parse(self):
        description = (
            "folder.tags to tags.m3u maker"
        )
        epilog = (
            "Examples:\n"
            "  %(prog)s\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument('-a',  '--autotrack',  help="Add autotrack tag", action='store_true')
        p.add_argument('-s',  '--skip-tags',  help="List of tags to skip", nargs='*')
        p.add_argument('-ng',  '--no-globaltags',  help="Don't convert repeated tags to global tags", action='store_true')
        p.add_argument('-nj',  '--no-join',  help="Don't join repeated tags (like multiple ARTIST)", action='store_true')
        p.add_argument('-ns',  '--no-sort',  help="Don't sort by TRACKNUMBER/TRACK", action='store_true')
        return p.parse_args()


    def _process(self):
        paths = os.listdir()
        paths.sort() #just in case

        with open(self.FILENAME_IN, 'rb') as infile:
            data = infile.read()

        id, = struct.unpack_from('12s', data, 0x00)
        if id != b'EXTERNALTAGS':
            print("unknown externaltags format")
            return

        offset = 0x0c
        while True:
            if offset == len(data):
                break
            base = offset

            filename_size, = struct.unpack_from('<I', data, offset)
            offset += 0x04

            filename, = struct.unpack_from('%ss' % (filename_size), data, offset)
            offset += filename_size

            subsong, = struct.unpack_from('<I', data, offset)
            offset += 0x04

            maxsize, = struct.unpack_from('<I', data, offset)
            offset += 0x04

            tags = []
            while offset < base + maxsize:
                tagname_size, = struct.unpack_from('<I', data, offset)
                offset += 0x04

                tagname, = struct.unpack_from('%ss' % (tagname_size), data, offset)
                offset += tagname_size

                tagvalue_size, = struct.unpack_from('<I', data, offset)
                offset += 0x04

                tagvalue, = struct.unpack_from('%ss' % (tagvalue_size), data, offset)
                offset += tagvalue_size


                tagname = tagname.decode("utf-8") 
                tagvalue = tagvalue.decode("utf-8") 

                #normalize for other players
                if tagname == 'ALBUM ARTIST':
                    tagname = 'ALBUMARTIST'

                #join repeated tags (needed for separate ARTISTS)
                new_tag = True
                if not self._args.no_join:
                    for idx, tag in enumerate(tags):
                        prev_tagname, prev_tagvalue = tag
                        if prev_tagname == tagname:
                            prev_tagvalue += ', %s' % (tagvalue)
                            entry = (prev_tagname, prev_tagvalue)
                            tags[idx] = entry
                            new_tag = False

                if new_tag:
                    entry = (tagname, tagvalue)
                    tags.append(entry)
                
                
                
            filename = filename.decode("utf-8") 
            
            entry = (filename, subsong, tags)
            self._files.append(entry)

            if filename in self._subsongs:
                self._subsongs[filename] += 1
            else:
                self._subsongs[filename] = 1


        # globals info after processing since some tags are joined
        globalcounts = collections.OrderedDict()
        for filename, subsong, tags in self._files:
            for tagname, tagvalue in tags:
                globalkey = tagname.upper()
                if globalkey in globalcounts and globalkey not in self._skip_global:
                    prev_tagname, prev_tagvalue, prev_count = globalcounts[globalkey]
                    if prev_tagvalue.upper() == tagvalue.upper():
                        prev_count += 1
                    entry = (prev_tagname, prev_tagvalue, prev_count)
                else:
                    entry = (tagname, tagvalue, 1)
                globalcounts[globalkey] = entry


        filecount = len(self._files)
        if filecount and not self._args.no_globaltags:
            for tagname, tagvalue, count in globalcounts.values():
                if filecount != count:
                    continue
                entry = tagname, tagvalue
                self._globaltags.append(entry)
                self._globaltagsnames[tagname] = 1
            
        return

    def _write(self):
        #normalize
        skips = [s.upper() for s in self._args.skip_tags or []]
        
        if not self._files:
            print("no files found")
            return

        # try reordering files by TRACKNUMBER if exists
        if self._args.no_sort:
            sorted_files = self._files
        else:
            sorted_files = sorted(self._files, key=sorter)

        with open(self.FILENAME_OUT, 'w', newline="\r\n", encoding='utf-8-sig') as outfile:
            #outfile.write('\xEF\xBB\xBF')#utf8-bom


            for tagname, tagvalue in self._globaltags:
                if skips and tagname.upper() in skips:
                    continue

                if ' ' in tagname:
                    outfile.write("# @%s@  %s\n" % (tagname, tagvalue))
                else:
                    outfile.write("# @%s  %s\n" % (tagname, tagvalue))

            if self._args.autotrack:
                outfile.write("# $AUTOTRACK\n")

            if self._globaltags or self._args.autotrack:
                outfile.write("\n")


            for filename, subsong, tags in sorted_files:

                for tagname, tagvalue in tags:
                    if tagname in self._globaltagsnames:
                        continue
                    if skips and tagname.upper() in skips:
                        continue
               
                    if self._args.autotrack:
                        if tagname.upper() in track_tags:
                            continue

                    if ' ' in tagname:
                        outfile.write("# %%%s%%  %s\n" % (tagname, tagvalue))
                    else:
                        outfile.write("# %%%s  %s\n" % (tagname, tagvalue))
                

                if subsong > 1 or subsong == 1 and self._subsongs[filename] > 1:
                    outfile.write('%s #%s.txtp\n' % (filename, subsong))
                else:
                    outfile.write('%s\n' % (filename))

        print("done")


    def start(self):
        self._args = self._parse()
        self._process()
        self._write()


# #####################################

if __name__ == "__main__":
    ExtTagsMaker().start()
