# GENERIC DOWNLOADER
# by bnnm
#
# usage:
# - create url.txt
# - write config like "command: (value)" (all commands are optional)
# - write urls
# - execute and wait
#
# example of url.txt
#   out: test                                   # sets base output dir (defaults to 'out')
#   prefix: https://test.com                    # sets prefix part for partial URLs
#   suffix: .ogg                                # sets end part for partial URLs
#   cut: assets/                                # makes folders after (not including) that part, otherwise after host
#   filter: *.ogg, *bgm/*                       # only downloads from URLs/names that match one of those (comma-separated) filters
#   header: User-Agent=FakeBrowser              # sets header values that may be verified by host (format: key=value)
#   header: X-Unity-Version=2019.4.2f1          # another header
#   threads: 10                                 # sets max simultaneous downloads (set 1 to disable)
#   name: path/file.out                         # sets next url's file name (may be defined multiple times)
#   debug: true                                 # don't download
#
#   # from the above config, would this download files to (current dir)/test/bgm/file.ogg
#   https://test.com/assets/bgm/file1.ogg       # full URL, downloads directly (no prefix/suffix)
#   assets/bgm/file2                            # partial URL, joins prefix/suffix above + this (if any)
#   assets/sfx/file3                            # partial URL

import os, sys, fnmatch, argparse
import ssl, urllib.request
import multiprocessing.dummy

class Downloader(object):
    def __init__(self):
        self.threads = 25
        self.prefix = None
        self.suffix = None
        self.cut = None
        self.filters = []
        self.headers = []
        self.urls = []
        self.out = 'out/'
        self.debug = False
        self.name = None
        self.filevar = None

        self._configs = {
            'out:': self._parse_out,
            'folder:': self._parse_out,

            'thread:': self._parse_threads,
            'threads:': self._parse_threads,

            'url:': self._parse_prefix,
            'prefix:': self._parse_prefix,
            'suffix:': self._parse_suffix,

            'cut:': self._parse_cut,
            'part:': self._parse_cut,
            
            'filter:': self._parse_filters,
            'filters:': self._parse_filters,

            'header:': self._parse_header,
            'headers:': self._parse_header,

            'debug:': self._parse_debug,

            'name:': self._parse_name,
            'filevar:': self._parse_filevar,
        }

    def _parse_threads(self, config):
        count = int(config)
        if count <= 0 or count >= 10000:
            print('ignored wrong thread count')
            return
        self.threads = count

    def _parse_name(self, name):
        self.name = name

    def _parse_filevar(self, filevar):
        self.filevar = filevar

    def _parse_out(self, config):
        if config and not config.endswith('/'):
            config += '/'
        self.out = config

    def _parse_prefix(self, config):
        if not config.endswith('/') and not '?' in config:
            config += '/'
        self.prefix = config

    def _parse_suffix(self, config):
        self.suffix = config

    def _parse_cut(self, config):
        self.cut = config

    def _parse_filters(self, config):
        filters = config.split(',')
        for filter in filters:
            filter = filter.strip()
            if filter:
                self.filters.append(filter)

    def _parse_header(self, config):
        keyval = config.split('=', 1)
        header = (keyval[0],keyval[1])

        self.headers.append(header)

    def _parse_debug(self, config):
        self.debug = True

    def _parse_config(self, line):
        if line.startswith('http'): #full URL
            return False

        index = line.find(':')
        if index < 0: #partial URL
            return False

        try:
            key = line[:index+1]
            val = line[index+1:].strip()

            callback = self._configs.get(key);
            if not callback:
                print("unknown config value:", line)
            else:
                callback(val)
        except:
            print("ignored wrong config value:", line)

        return True


    def _add_url(self, line):

        if line.startswith('http'):
            url = line
        else:
            url = line
            if url.startswith('/'):
                url = url[1:]
            if self.prefix:
                url = self.prefix + url
            if self.suffix:
                url = url + self.suffix

        url = url.replace(' ', '%20')

        # ignore non-matching urls/names
        if self.filters:
            matched = False
            for filter in self.filters:
                #if filter in url:
                if fnmatch.fnmatch(url, filter):
                    matched = True
                    break
                #if self.name and filter in self.name:
                if self.name and fnmatch.fnmatch(self.name, filter):
                    matched = True
                    break
            if not matched:
                return

        # output path
        if self.name:
            path = self.name
            self.name = None #consume to avoid overwrites
        elif self.cut == '?':
            path = url.rsplit('/', 1)[1]
        elif self.cut and self.cut in url:
            path = url.split(self.cut)[1]
        else:
            pos = url.find("/", 10) #after https://
            path = url[pos+1:]

        if not path:
            path = 'index'

        if self.out:
            path = self.out + path

        # remove query string
        if '?' in path:
            path, query = path.split('?', 1)
            if self.filevar: #use filename from query if set
                vars = query.split('&')
                for var in vars:
                    key, val = var.split('=', 1)
                    if key != self.filevar:
                        continue
                    if '/' in path: #include filevar in output path
                        path = path[0:path.rfind('/')+1] + val
                    else:
                        path = val

        for rep in "*<>:|?\"":
            path = path.replace(rep, '_')
        item = (url, path)
        if item in self.urls:
            return
        self.urls.append(item)

    def _read(self, filename=None, vars=None):
        if not filename:
            filename = 'url.txt'

        if not os.path.exists(filename):
            print("filename not found")
            return

        print("reading %s" % (filename))
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                #print(line)

                if not line or line.startswith('#'):
                    continue
                
                if vars:
                    for key,value in vars:
                        line = line.replace("{%s}" % (key), value)

                is_config = self._parse_config(line)

                # current line was config
                if is_config:
                    continue

                # current line is URL(-like)
                self._add_url(line)


    def _download(self, url, path):
        if self.debug:
            print((url, path))
            return

        try:
            try:
                # output dir
                dir = os.path.dirname(path)
                if not dir.endswith('/'):
                    dir = dir + '/'
                    
                if not os.path.exists(dir):
                    os.makedirs(dir)
            except Exception as e:
                # threaded so could clash
                #print("can't make path: ", dir)
                pass

            urllib.request.urlretrieve(url, path)
            
            with self.counter.get_lock():
                self.counter.value += 1
            
        except Exception as e:
            print("error with url:\n- url: %s\n- path: %s\n- %s" % (url, path, e))


    def _launch(self):
        print("downloading files")

        # ignore bad certs
        ssl._create_default_https_context = ssl._create_unverified_context
        
        proxy = urllib.request.ProxyHandler()
        opener = urllib.request.build_opener(proxy)
        if self.headers:
            opener.addheaders = self.headers
        urllib.request.install_opener(opener)

        self.counter = multiprocessing.Value('i', 0)

        if self.threads == 1:
            # disable pool for single threaded
            for url, path in self.urls:
                self._download(url, path)
        else:
            pool = multiprocessing.dummy.Pool(self.threads)
            pool.starmap(self._download, self.urls)

            # divide into lists of max N elems
            #chunks = [self.urls[i:i + self.threads] for i in range(0, len(self.urls), self.threads)]

            #for chunk in chunks:
            #    pool.starmap(self._download, chunk)

        print("downloaded %i of %i" % (self.counter.value, len(self.urls)))


    def start(self, filename=None, vars=None):
        self._read(filename, vars)
        self._launch()


class Cli(object):
    def _parse(self):
        description = (
            "Downloads from url txt file"
        )
        epilog = (
            "examples:\n"
            "  %(prog)s *.txt\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument('files', help="Files to get (wildcards work)", nargs='+')
        p.add_argument('-v', dest='vars', help="Set key=value variables, replacing {key} in .txt", nargs='*')
        return p.parse_args()
    
    def _read_map(self, filename):
        vars = []
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                if not line or line.startswith('#'):
                    continue

                if line.endswith('.txt'):
                    file = line
                    Downloader().start(file, vars)
                    vars = []
                    continue

                keyval = line.split("=", 1)
                vars.append( (keyval[0], keyval[1]) )


    def start(self):
        args = self._parse()
        
        vars = []
        if args.vars:
            for var in args.vars:
                keyval = var.split("=", 1)
                vars.append( (keyval[0], keyval[1]) )
        
        for file in args.files:
            if file.endswith('.map'):
                self._read_map(file)
            else:
                Downloader().start(file, vars)


if __name__ == "__main__":
    Cli().start()
