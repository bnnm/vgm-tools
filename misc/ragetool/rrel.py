import rdefs
import rprinter

class RelObject():
    def __init__(self, hash, type):
        self.hash = hash
        self.type = type
        # other fields are added dynamically

    def add_field(self, name, value):
        setattr(self, name, value)

class RelParser():

    def __init__(self, reader, hasher):
        self._r = reader
        self._hasher = hasher
        self._printer = rprinter.RagePrinter()

        #self._depth = 0
        #self.lines = []
        self.scripts = {}
        self.sounds = {}

    # ---------------------------------------------------------------------------------

    def add(self, text):
        self._printer.add(text)
        return self

    def next(self):
        self._printer.next()
        return self
    
    def prev(self):
        self._printer.prev()
        return self

    def print(self):
        self._printer.print()

    def save(self):
        outfile = self._r.file + '.txt'
        self._printer.save(outfile)

    # ---------------------------------------------------------------------------------

    def find_set_bits(self, value):
        set_bits = []
        bit_position = 0
        for i in range(64):
            if value & 1:  # Check if the last bit is set
                set_bits.append(bit_position)
            value >>= 1  # Shift the value right by one bit
            bit_position += 1
        return set_bits

    def read_bitflags(self):
        bitflags = self._r.u64()
        bitflags_fields = [
            (1<<0,  'u32', 'flags'),
            (1<<1,  's16', 'bit01'),
            (1<<2,  's16', 'bit02'),
            (1<<3,  's16', 'bit03'),
            (1<<4,  's16', 'bit04'),
            (1<<5,  's16', 'bit05'),
            (1<<6,  's16', 'bit06'),
            (1<<7,  's16', 'bit07'),
            (1<<8,  's16', 'bit08'),
            (1<<9,  's16', 'bit09'),
            (1<<10, 's32', 'bit10'),
            (1<<11, 's32', 'bit11'),
            (1<<12, 's16', 'bit12'),
            (1<<13, 's16', 'bit13'),
            (1<<14, 's16', 'bit14'),
            (1<<15, 's16', 'bit15'),
            (1<<16, 'hash','category'),
            (1<<17, 's16', 'bit17'),
            (1<<18, 's16', 'bit18'),
            (1<<19, 's16', 'bit19'),
            (1<<20, 's16', 'bit20'),
            (1<<21, 'hash','bit21'),
            (1<<22, 's16', 'bit22'),
            (1<<23, 'u8',  'bit23'),
            (1<<24, 'u8',  'bit24'),
            (1<<25, 's16', 'bit25'),
            (1<<26, 's16', 'bit26'),
            (1<<27, 'u8',  'bit27'),
            (1<<28, 'u8',  'bit28'),
            (1<<29, 'u8',  'bit29'),
            (1<<30, 'hash','bit30'),
            (1<<31, 'hash','bit31'),
            (1<<32, 'hash','bit32'),
            (1<<33, 'hash','bit33'), #check
            (1<<34, 'hash','bit34'),
            (1<<35, 'hash','bit35'),
            (1<<36, 'hash','bit36'),
            (1<<37, 'hash','bit37'),
            (1<<38, 's16', 'bit38'),
            (1<<39, 's16', 'bit39'),
            (1<<40, 's16', 'bit40'),
            (1<<41, 's16', 'bit41'),
            (1<<42, 's16', 'bit42'),
            (1<<43, 's16', 'bit43'),
            (1<<44, 's16', 'bit44'), #check
            (1<<45, 's16', 'bit45'),
            (1<<46, 0,     'bit46'),
            (1<<47, 0,     'bit47'),
            (1<<48, 0,     'bit48'),
            (1<<49, 0,     'bit49'),
            (1<<50, 0,     'bit50'),
            (1<<51, 0,     'bit51'),
            (1<<52, 0,     'bit52'),
            (1<<53, 0,     'bit53'),
            (1<<54, 0,     'bit54'),
            (1<<55, 0,     'bit55'),
            (1<<56, 0,     'bit56'),
            (1<<57, 0,     'bit57'),
            (1<<58, 0,     'bit58'),
            (1<<59, 0,     'bit59'),
            (1<<60, 0,     'bit60'),
            (1<<61, 0,     'bit61'),
            (1<<62, 0,     'bit62'),
            (1<<63, 0,     'bit63'),
        ]
        bitflags_registers = [
            (1<<16)
        ]
        

        for bit, size, name in bitflags_fields:
            if bitflags & bit == 0:
                continue

            if   size == 'hash':
                if bit in bitflags_registers:
                    self.read_hash(name, context=name)
                else:
                    self.read_hash(name)
            elif   size == 'u32':
                self.read_u32(name)
            elif   size == 's32':
                self.read_s32(name)
            elif size == 's16':
                self.read_s16(name)
            elif size == 'u8':
                self.read_u8(name)
            else:
                # not seen in proj_sounds.dat98.rel
                raise ValueError("unknown bitflag %08x" % (bit))


    def read_test(self, name='unk'):
        self.read_link(name=name, test=True)

    def read_hash(self, name='hash', context=None):
        return self.read_link(name=name, little_endian=True, context=context)

    def read_awcc(self, name='hash'):
        return self.read_link(name=name, little_endian=True, awc_hash=True)

    def read_link(self, name='link', test=False, context=None, little_endian=False, awc_hash=False):
        r = self._r
        if little_endian:
            link = r.u32()
        else:
            link = r.u32be()
        if test and (link != 0 and link != 0xFFFFFFFF):
            raise ValueError('unknown link found %08x' % (link) )

        str = ''
        if link == 0:
            str = 'none'
        elif link == 0xffffffff:
            str = 'unset'
        else:
            str = self.hname(link, context=context, awc_hash=awc_hash)
        self.add('%-10s  %s' % (name, str))

        return self.add_temp(name, link)

    def read_links(self, name='links'):
        count = self._r.u8()

        links = []
        self.add(name).next()
        for i in range(count):
            self.read_link()
            links.append(self.lastval)
        self.prev()

        return self.add_temp(name, links)

    def read_hashes(self):
        count = self._r.u8()
        self.add('hashes').next()
        for i in range(count):
            self.read_hash()
        self.prev()

    def read_links32(self, name='links32'):
        count = self._r.u32()
        self.add(name).next()
        links = []
        for i in range(count):
            self.read_link()
            links.append(self.lastval)
        self.prev()

        return self.add_temp(name, links)

    def read_script_header(self):
        self.read_u16()
        self.read_u8()

    def read_flags(self):
        self.read_u32('flags')

    def read_f32(self, name='num'):
        value = self._r.f32()
        self.add('%-10s  %f' % (name, value))
        return self.add_temp(name, value)

    def read_s32(self, name='num'):
        value = self._r.s32()
        self.add('%-10s  %i' % (name, value))
        return self.add_temp(name, value)

    def read_u32(self, name='num'):
        value = self._r.u32()
        self.add('%-10s  %08x' % (name, value))
        return self.add_temp(name, value)

    def read_s16(self, name='num'):
        value = self._r.s16()
        self.add('%-10s  %i' % (name, value))
        return self.add_temp(name, value)

    def read_u16(self, name='num'):
        value = self._r.u16()
        self.add('%-10s  %04x' % (name, value))
        return self.add_temp(name, value)

    def read_u8(self, name='num'):
        value = self._r.u8()
        self.add('%-10s  %02x' % (name, value))
        return self.add_temp(name, value)

    # register temporally last added names
    def add_temp(self, name, value):
        self.lastname = name
        self.lastval = value
        return self

    def update(self, obj):
        obj.add_field(self.lastname, self.lastval)

    # ---------------------------------------------------------------------------------

    def parse_script(self, hash, size):
        r = self._r
        current = r.pos() #save
        chunk = r.chunk(size)
        r.pos(current) #goto

        self.next()
       
        type = r.u8()
        description = rdefs.REL325_SCRIPT_TYPES.get(type, '?')
        self.hregister(hash, 'SCRIPTS %02x [%s]' % (type, description))

        self.add('%02x [%s]' % (type, description))
        self.add('%s %s' % (chunk[0:1].hex(), chunk[1:].hex()))

        obj = RelObject(hash, type)
        self.scripts[hash] = obj

        # not correct
        #if type == 0x21: #
        #    self.read_script_header()
        #    self.read_s16()
        #    self.read_hash() #actually a link
        #    self.read_hashes()
        #    self.read_hashes()
        #    self.read_u8()
        #    self.read_u8()
        #    self.read_u8()

        #if type >= 0x40 and type >= 0x43:
        #    raise ValueError("unknown type found")

        # layer volume info
        if type == 0x44: #StemMix
            self.read_script_header()
            volumes = []
            for i in range(12):
                self.read_s16('vol%02i' % i)
                volumes.append(self.lastval)
            obj.add_field('volumes', volumes)


        if type == 0x45:
            raise ValueError("unknown type found")

        if type == 0x46: #StemMixFloat
            self.read_script_header()
            volumes = []
            for i in range(12):
                self.read_f32('vol%02i' % i)
                volumes.append(self.lastval)
            obj.add_field('volumes', volumes)

        if type == 0x47:
            raise ValueError("unknown type found")

        if type == 0x48:
            raise ValueError("unknown type found")

        if type == 0x49: #InteractiveMusicMood
            self.read_script_header()
            self.read_flags()
            self.read_s16('fadein')
            self.read_s16('fadein')
            self.read_f32() #0
            self.read_link('mood').update(obj)
            for i in range(32):
                self.read_f32()

            stems = []
            count = r.u32()
            self.add('stems').next()
            for i in range(count):
                self.read_link('stem')
                stems.append(self.lastval)
                self.read_link('stop') #-1 or StopTrackAction
                self.read_f32()
                self.read_f32()
                self.read_f32()
                self.read_s32() #0/1
                self.read_link('bar')
                self.read_test() #-1
            self.prev()
            obj.add_field('stems', stems)

        if type == 0x4a: #StartTrackAction
            self.read_script_header()
            self.read_flags()
            self.read_test() #0
            self.read_s32() #0/1
            self.read_link() #54-55, bar?
            self.read_test() #-1 beat?
            self.read_f32()
            self.read_hash('sound').update(obj)
            self.read_link('mood').update(obj)
            self.read_test() #0
            self.read_s32()
            self.read_s32()
            self.read_f32() #0
            self.read_s32()
            self.read_link('stem_f32').update(obj)

            # rare, usually various related sounds (one after other?)
            self.add('sounds').next()
            sounds = []
            count = r.u32()
            for i in range(count):
                self.read_hash()
                sounds.append(self.lastval)
                self.read_test() #0
            self.prev()
            obj.add_field('sounds', sounds)

        if type == 0x4b: #StopTrackAction
            self.read_script_header()
            self.read_flags()
            self.read_s32() #0/1
            self.read_s32() #0/1
            self.read_link('beat') #-1/num
            self.read_link('bar') #-1/num
            self.read_f32()
            self.read_s32()
            self.read_link('stem_f32')

        if type == 0x4c: #SetMoodAction
            self.read_script_header()
            self.read_flags()
            self.read_test() #0
            self.read_s32() #0/1
            self.read_link('beat')
            self.read_link('bar')
            self.read_f32()
            self.read_link('mood').update(obj)
            self.read_s32()
            self.read_s32()
            self.read_s32()
            self.read_link('stem_f32a').update(obj)
            self.read_link('stem_f32b').update(obj)
            
        #
        if type == 0x4d: #Stop?
            raise ValueError("unknown type found")

        # seems to call other types
        if type == 0x4e: #StartActionList
            self.read_script_header()
            self.read_links32('actions').update(obj)

        if type == 0x4f: #StopActionList
            self.read_script_header()
            self.read_flags()
            self.read_test() #0
            self.read_test() #0
            self.read_test() #-1 bar?
            self.read_test() #-1 beat?
            self.read_f32()
            self.read_s32()
            self.read_f32() #0
            self.read_s32()
            self.read_s32()
            self.read_f32()
            self.read_test() #0
            self.read_s32()

        #
        if type == 0x50:
            self.read_script_header()
            self.read_flags()
            self.read_test() #0
            self.read_test() #0
            self.read_test() #-1 beat?
            self.read_test() #-1 bar?
            self.read_test() #0
            self.read_s32()
        #
        if type == 0x51:
            self.read_script_header()
            self.read_flags()
            self.read_test() #0
            self.read_test() #0
            self.read_test() #-1 beat?
            self.read_test() #-1 bar?
            self.read_f32()
            self.read_s32() #low num
            self.read_f32()
            self.read_s32()
            self.read_s32()
            self.read_test() #0

        #
        if type == 0x52: #StartOneShotAction
            self.read_script_header()
            self.read_flags()
            self.read_test() #0
            self.read_s32() #0/1
            self.read_link('beat')
            self.read_link('bar')
            self.read_f32()
            self.read_hash('sound').update(obj)
            self.read_s32()
            self.read_s32()
            self.read_s32()

            self.read_test() #0
            self.read_f32()
            self.read_f32()
            self.read_f32()
            self.read_f32()
            
            self.read_test() #0
            self.read_f32()
            self.read_f32()

        if type == 0x53: #StopOneShotAction
            self.read_script_header()
            self.read_flags()
            self.read_s32() #0/1
            self.read_s32() #0/1
            self.read_link('beat') #-1/num
            self.read_link('bar') #-1/num
            self.read_f32()
            self.read_hash('sound')
            self.read_s32()

        if type == 0x54: #MusicBeat
            self.read_script_header()
            self.read_u16() #5555 7777 1110 1000 ...

        if type == 0x55: #MusicBar
            self.read_script_header()
            self.read_s32('bars')
            self.read_s32('div')
        
        #if type == 0x57: #long list of floats
        #if type == 0x58: #long list of floats and some hashes?

        if type == 0x59: #
            self.read_script_header()
            self.read_flags()
            self.read_f32()
            self.read_f32()
            self.read_s16()
            self.read_s16()
            self.read_hash()

        if type == 0xFF: #some kind simple index (groups of events? stops, mood actions, etc)
            self.read_script_header()
            
            count = r.u32()
            self.add('refs').next()
            for i in range(count):
                self.read_hash() #internal link but LE
                self.read_u32('offset')
            self.prev()

            self.read_s32()
            self.read_s32()

        self.prev()

    def parse_sound(self, hash, size):
        r = self._r
        current = r.pos() #save
        chunk = r.chunk(size)
        r.pos(current) #goto

        self.next()
       
        type = r.u8()
        description = rdefs.REL98_SOUND_TYPES.get(type, '?')
        self.hregister(hash, 'SOUNDS %02x [%s]' % (type, description))

        self.add('%02x [%s]' % (type, description))
        if type >= 0x00 and type < 0x29:
            self.add('%s %s %s' % (chunk[0:1].hex(), chunk[1:9].hex(), chunk[9:].hex()))
        else:
            self.add('%s %s' % (chunk[0:1].hex(), chunk[1:].hex()))

        obj = RelObject(hash, type)
        self.sounds[hash] = obj

        #if type < 0x29 and type not in (0x07, 0x08, 0x0c, 0x0d): #unsure about 0x28, not all numbers exist
        #    self.add('bitflags  %016x [%s]' % (bitflags, self.find_set_bits(bitflags)))

        # 
        if type == 0x01: #LoopingSound
            self.read_bitflags()
            self.read_s16('loopcount')
            self.read_s32('variance')
            self.read_link('sound')
            self.read_hash('LoopCountVariable?') #0 

        # 
        if type == 0x02: #EnvelopeSound
            self.read_bitflags()
            self.read_s16() #Attack?
            self.read_s16() #AttackVariance?
            self.read_s16() #Decay?
            self.read_s16() #DecayVariance?
            self.read_s16() #Sustain?
            self.read_s16() #SustainVariance
            self.read_s16() #SustainX?
            self.read_s16() #Hold?
            self.read_s16() #HoldVariance?
            self.read_s16() #HoldX?
            self.read_s16() #Release?
            self.read_s16() #ReleaseVariance?
            self.read_hash('AttackCurve?')
            self.read_hash('DecayCurve?')
            self.read_hash('ReleaseCurve?')
            self.read_hash('AttackVariable?')
            self.read_hash('DecayVariable?')
            self.read_hash('SustainVariable?')
            self.read_hash('HoldVariable?')
            self.read_hash('ReleaseVariable?')

            self.read_link('sound')
            self.read_s32() #0/1
            self.read_hash('OutputVariable?')
            self.read_u8('Mode?')
            self.read_f32('OutputRangeMin?')
            self.read_f32('OutputRangeMax?')
            
        #0x03: 'TwinLoopSound',
        #0x04: 'SpeechSound',

        # if child is met uses StopSound, or Fallback
        if type == 0x05: #OnStopSound
            self.read_bitflags()
            self.read_link('ChildSound')
            self.read_link('StopSound')
            self.read_link('FallbackSound')

        # play one or other sound with variables
        if type == 0x06: #WrapperSound
            self.read_bitflags()

            self.read_link('ChildSound')
            self.read_s32('LastPlayTime?')
            self.read_link('Settings?')
            self.read_hash('FallBackSound?') #hash!
            self.read_s32() #MinRepeatTime?
            self.read_s16()

            count = self._r.u8()
            self.next()
            for i in range(count):
                self.read_hash()
                self.read_u8()
            self.prev()

        # play list of N sounds
        if type == 0x07: #SequentialSound
            self.read_bitflags()
            self.read_s16()
            self.read_links('Sounds')

        # seem to define N awc-channels to play at once (silence via events)
        if type == 0x08: #StreamingSound
            self.read_bitflags()
            self.read_s32('Duration')
            self.read_u8()
            self.read_links('sounds').update(obj)

        if type == 0x09: #RetriggeredOverlappedSound
            self.read_bitflags()
            self.read_s16('LoopCount')
            self.read_s16('LoopCountVariance')
            self.read_s16('DelayTime')
            self.read_s16('DelayTimeVariance')
            self.read_hash('LoopCountVariable')
            self.read_hash('DelayTimeVariable')
            self.read_link('StartSound')
            self.read_link('RetriggerSound')
            self.read_link('StopSound')
            self.read_u8() #0/1

        if type == 0x0a: #CrossfadeSound
            self.read_bitflags()
            self.read_link('NearSound')
            self.read_link('FarSound')
            self.read_u8('Mode') #0/1
            self.read_f32('MinDistance')
            self.read_f32('MaxDistance')
            self.read_f32('Hysteresis')
            self.read_hash('CrossfadeCurve')
            self.read_test('DistanceVariable')
            self.read_test('MinDistanceVariable')
            self.read_test('MaxDistanceVariable')
            self.read_test('HysteresisVariable')
            self.read_hash('CrossfadeVariable')

        if type == 0x0b: #CollapsingStereoSound
            self.read_bitflags()
            self.read_link('LeftSound')
            self.read_link('RightSound')
            self.read_f32('MinDistance')
            self.read_f32('MaxDistance')
            self.read_hash('MinDistanceVariable')
            self.read_hash('MaxDistanceVariable')
            self.read_hash('CrossfadeOverrideVariable')
            self.read_hash()
            self.read_hash()
            self.read_f32()
            self.read_test()
            self.read_u8('Mode') #0/1

        # individual channel inside a .awc
        if type == 0x0c: #SimpleSound
            self.read_bitflags()
            self.read_awcc('awc').update(obj) #ContainerName
            self.read_awcc('channel').update(obj) #FileName
            self.read_u8('WaveSlot?')
            self.read_s32() #0/1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1
            self.read_test() #-1


        # play N sounds of N channels
        if type == 0x0d: #MultitrackSound
            self.read_bitflags()
            self.read_links('sounds').update(obj)

        #if type == 0x0e: #RandomizedSound

        if type == 0x0f: #EnvironmentSound
            self.read_bitflags()
            self.read_u8()
            self.read_test()

        if type == 0x10: #DynamicEntitySound
            self.read_bitflags()
            self.read_hashes()

        # 
        if type == 0x16: #SwitchSound
            self.read_bitflags()
            self.read_hash()
            self.read_u8()
            self.read_links('Sounds')

        # 
        if type == 0x1f: #ExternalStreamSound
            self.read_bitflags()
            self.read_links('EnvironmentSounds')
            self.read_test()
            self.read_test()

        if type == 0x23: #ContextSound
            self.read_bitflags()
            self.read_link('Sound')
            self.read_s16() #0
            self.read_u8() #2

            self.add('entries').next()
            count = r.u8()
            for i in range(count):
                self.read_hash()
                self.read_link()
            self.prev()

        if type == 0x29: #SoundSet
            self.read_flags()

            count = r.u32()
            self.next()
            for i in range(count):
                self.read_hash('script?')
                self.read_link()
                self.read_u32()
            self.prev()

        self.prev()

    def hregister(self, hash, context):
        self._reltype
        self._hasher.register(hash, context)

    def hname(self, hash, context=None, awc_hash=False):
        if awc_hash:
            context = 'awc-channels'

        #if hash == 0xFFFFFFFF:
        #    return '-1'

        self._hasher.register(hash, context)
            
        str = '0x%08x' % hash
        hname = self._hasher.get(hash, awc_hash)
        if hname:
            str += '  ' + hname #.decode('utf-8')
        return str

    def parse_hash_table(self):
        r = self._r
        self.add("HashTable").next()
        pos = r.pos()

        size = r.u32()
        entries = r.u32()

        #self.add('size      %08x' % size)
        self.add('entries   %u' % entries)

        hashes_offset = pos + 0x08 + entries * 0x08
        for i in range(entries):
            index = r.u32()
            count = r.u32()
            #self.add("index    %08x" % (index))
            #self.add("count    %08x" % (count))
            #self.add("Item %i" % (i)).next()

            entry_pos = r.pos()
            r.pos(hashes_offset + index * 0x04)
            #items = []
            for j in range(count):
                hash = r.u32()
                #items.append(hash)
                self.add('%i %s' % (j, self.hname(hash)))

            #hashes = ','.join(['%08x' % hash for hash in items])
            #self.add('%04i: %s' % (i, hashes))
            #self.add("Item %i" % (i)).next()

            r.pos(entry_pos)

            #self.prev()
            
        r.pos(pos + 0x04 + size)

        self.prev().add('')

    def parse_name_table(self):
        r = self._r
        self.add("NameTable").next()
        pos = r.pos()

        size = r.u32()
        entries = r.u32()

        self.add('size      %08x' % size)
        self.add('entries   %u' % entries)

        # names in unknown encryption
        # GTA5 only had .AWC names/paths though (not event names)

        r.pos(pos + 0x04 + size)
        self.prev().add('')

    def parse_items(self, type):
        r = self._r
        self.add("ItemTable").next()
        
        entries = r.u32()

        self.add('entries   %u' % entries)

        for i in range(entries):
            hash = r.u32() #LE!
            offset = r.u32()
            size = r.u32()

            self.next()
            self.add("%s" % (self.hname(hash)))

            pos = r.pos() #save
            r.pos(offset + 0x8) #goto
            try:
                if type == 98:
                    self.parse_sound(hash, size)
                if type == 325:
                    self.parse_script(hash, size)

                if r.pos() > offset + 0x8 + size:
                    raise ValueError("Read past object")

            except ValueError as e:
                r.pos(offset + 0x8) #goto
                chunk = r.chunk(size)
                raise ValueError("error while parsing %s" % (chunk.hex())) from e

            r.pos(pos)

            self.prev()

        self.prev().add('')

    def parse_table2(self):
        r = self._r
        self.add("OffsetTable").next()
        
        entries = r.u32()
        self.add('entries   %u' % entries)

        for i in range(entries):
            offset = r.u32()

            #self.add("Item %i" % (i))
            #self.next()
            #self.add("offset %08x" % (offset)) #within some section
            #self.prev()

        self.prev().add('')
   

    def parse(self):
        r = self._r
        
        self.add(f'{self._r.file}').next()

        reltype = r.u32()
        tables_offset = r.u32()
        id = r.u32()
        
        self._reltype = reltype
        
        # proj_sounds.dat98.rel
        # proj_game.dat325
        if reltype not in (98, 325):
            self.add(f'unsupported REL type: {reltype}')
            return

        # seems to be consistent by package, but there are a bunch
        #if id not in (0x017BB6B4, 0x01A9F972, 0x01DC283A, 0x01D95604, 0x0178A476):
        #    self.add(f'not an valid RDR2 REL file')
        #    return

        # skip data block
        r.pos(tables_offset + 0x08)

        self.parse_hash_table()
        self.parse_name_table()
        self.parse_items(reltype)
        self.parse_table2()
        self.parse_table2()
        self.parse_table2()
