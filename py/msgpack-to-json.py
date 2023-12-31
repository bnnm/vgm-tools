# MSGPACK PRINTER
# - deps:
#   pip install msgpack
# - doesn't actually create well formed json but meh
import msgpack, os, sys


class MsgpackApp:

    def __init__(self, file):
        self.name = file
        with open(file, 'rb') as f:
            data = f.read()

        is_old = False
        strict_map_key = False #Theatrhythm Final Bar Line
        self.items = msgpack.unpackb(data, raw=is_old, strict_map_key=strict_map_key)

    # prints msgpack data
    def print_msgpack(self):
        self.msgs = []
        self._print_item(self.items, 0)

        outfile = self.name + '.msgpack.json'
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.msgs))

        self.msgs = None
    
    def _print_item(self, item, depth):
        #print( item )

        if isinstance(item, list):
            line = "%s[" % (' '*depth*2)
            self.msgs.append(line)
            #print(line)
            for subitem in item:
                self._print_item(subitem, depth+1)
            line = "%s]," % (' '*depth*2)
            self.msgs.append(line)
            #print(line)
        else:
            text = ''
            if isinstance(item, str):
                text = "'%s'" % (item)
            elif isinstance(item, dict):
                text = "'%s'" % (item)
            elif item is None:
                text = 'null'
            else:
                text = "0x%08x" % (item)

            line = "%s%s," % (' '*depth*2, text)
            self.msgs.append(line)
            #print(line)

def main():
    if len(sys.argv) <= 1:
        print("Usage: %s infile" % (os.path.basename(sys.argv[0])))
        return
    for infile in sys.argv[1:]:
        try:
            app = MsgpackApp(infile)
            app.print_msgpack()
        except e:
            print("couldn't parse: " + e.msg)

main()
