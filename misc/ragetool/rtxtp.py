import os

def get_awc_key(awc):
    file = awc
    file = os.path.basename(file)
    file = os.path.splitext(file)[0]

    path = os.path.dirname(awc)
    path = os.path.basename(path)
    #key = f'{path}/{file}'
    key = f'{file}'
    key = key.upper()
    return key

# .awc and layered channels
class TxtpTrack():
    def __init__(self, hasher):
        self._hasher = hasher
        self.awc = ''
        self.channels = [] # in order of playing
        self.events = []

    def _get_name(self, hash, awc_hash=False):
        name = self._hasher.get(hash, awc_hash=awc_hash)
        if not name:
            name = '0x%X' % (hash)
        return name

    def add_awc(self, hash):
        awc_name = self._get_name(hash, awc_hash=True)
        if self.awc and self.awc != awc_name:
            raise ValueError("different awc! %s vs %s" % (self.awc, awc_name))
        self.awc = awc_name

    def add_channel(self, hash):
        if hash in self.channels:
            raise ValueError("dupe channel!")
        self.channels.append(hash)

    def add_event(self, event):
        # detect if even already exists and join them
        self.events.append(event)

    def print(self):
        print('%s' % self.awc)
        for event in self.events:
            print('  %s' % (event.names))
            print('    %s' % (event.stem))


# events + moods that call a track, but to simplify this is inverted here (track points to N events w/moods)
# each mood (combo of sounds) will have a .txtp, 
# null/default mood can be used for oneshots
class TxtpEvents():
    def __init__(self, hasher):
        self._hasher = hasher
        self.stem = None
        self.names = set()
        self.oneshot = False
        self.unconfirmed = False #moods that may not belong here

    def _get_name(self, hash, awc_hash=False):
        name = self._hasher.get(hash, awc_hash=awc_hash)
        if not name:
            name = '0x%X' % (hash)
        return name

    def add_names(self, names):
        for name in names:
            self.names.add(name)

    def add_name_str(self, name):
        self.names.add(name)

    def add_name(self, hash):
        name = self._get_name(hash)
        #if name not in self.names:
        self.names.add(name)

    def put_stem(self, stem):
        if not stem:
            return
        if self.stem:
            raise ValueError("double stem")
        self.stem = stem

    def set_oneshot(self):
        self.oneshot = True

# Custom sort key function
def event_name_sorter(s):
    return (s.startswith("0x"), s)

class TxtpFormatter():

    def track_to_basefile(self, track):
        base_awc = os.path.basename(track.awc)
        return '%s.awc' % (base_awc)

    # TODO: improve algo to do less swaps
    def _get_remaps(self, track_channels, awc_streams):
        swaps = []
        unordered = awc_streams
        ordered = list(track_channels)
        curr = 0
        while unordered != ordered:
            hash = unordered[curr]
            pos = ordered.index(hash)

            if curr == pos:
                curr += 1
                continue
            
            swaps.append(f'{curr+1}-{pos+1}')
            temp = unordered[curr]
            unordered[curr] = unordered[pos]
            unordered[pos] = temp
        return swaps


    def track_to_remap(self, track, awcs):
        if not track.awc or not awcs:
            return ''

        key = get_awc_key(track.awc)
        awc = awcs.get(key)
        if not awc:
            key = os.path.basename(track.awc)
            awc = awcs.get(key)
        if not awc:
            key = os.path.basename(track.awc)
            key = os.path.splitext(track.awc)[0]
            awc = awcs.get(key)
        if not awc:
            return ''

        # AWC saves channels with a simplified hash and unordered 
        # track.channels = good order, awc.streams = bad order to be remapped
        channels = [ch & 0x1FFFFFFF for ch in track.channels]
        if awc.streams == channels:
            return ''

        swaps = self._get_remaps(channels, awc.streams)
        return ' #m ' + ','.join(swaps)

    def _clean_suffixex(self, name):
        suffixes = ['_MD', '_MOOD', '_MA', '_OW', '_OWC', '_SMA', '_STA', '_STO', '_MIX'] #order matters
        for suffix in suffixes:
            if not name.upper().endswith(suffix):
                continue
            name = name[:-len(suffix)]

        swaps = [('_CS_START', '_CS')]
        for suffix, swap in swaps:
            if not name.upper().endswith(suffix):
                continue
            name = name[:-len(suffix)] + swap

        return name

    def event_to_comment(self, event):
        final_names = []
        for name in event.names:
            if name not in final_names:
                final_names.append(name)
        final_names = sorted(final_names, key=event_name_sorter)
        return ",".join(final_names)

    # normalize event names that are a mix of BLAH_START, BLAH_START_MOOD, etc
    def event_to_info(self, event):
        if not event.names:
            return ''

        final_names = []
        for name in event.names:
            name = self._clean_suffixex(name)
            if name.startswith('0x'):
                continue
            if name not in final_names:
                final_names.append(name)
        if not final_names:
            return 'unknown'

        final_names = sorted(final_names, key=event_name_sorter)
        return ",".join(final_names)

    def event_to_loop(self, event):
        out = ''
        if not event.oneshot:
            out += ' #e'
        return out

    def stem_to_info(self, stem):
        if not stem:
            return ''

        if all(value <= -10000 for value in stem): #silent
            return 'SM_SILENCE'

        layers = []
        for i, volume in enumerate(stem):
            if volume > -10000:
                layers.append(f'{i+1}')

        return 'SM_' + '_'.join(layers) 

    def stem_to_commands(self, stem):
        if not stem:
            return ''

        if all(value <= -10000 for value in stem): #silent
            return ' #v 0.0'

        chs = []
        volumes = []

        for i, volume in enumerate(stem):
            # track N doesn't play = ignored
            if volume <= -10000:
                continue

            # layer N = stereo pair + 1 to txtp mapping
            ch_a = i * 2 + 0 + 1
            ch_b = i * 2 + 1 + 1

            # track N does play: convert to #C equivalent (assumes AWC layers are reordered first
            # since its order is not correct in .AWC but must be found in .dat98.rel)
            chs.extend([f'{ch_a}', f'{ch_b}'])
            if volume == 0:
                continue
            
            # track N does play and has a volume = convert to .txtp format
            # txtp: 1.0 = 100% volume (default) / 0.0 = 0% volume
            # rel:  0 = 100% = 1.0 / -10000 = -100.00% = 0.0 / -600 = -6.00? = 1.0 - 0.06 = 0.94?
            # TODO check if -600 = -6% or if logaritmic/etc
            volume += 10000
            volume = volume / 10000.0

            volumes.extend([f'{ch_a} * {volume}', f'{ch_b} * {volume}'])

        out = ''
        if chs:
            out += ' #C ' + ','.join(chs)
        if volumes:
            out += ' #m ' + ','.join(volumes)


        return out

