import os
import rtxtp, rgenerator_tree

TXTP_BASE = 'txtp/'

#TODO ignore awc not in parsed awc


class TxtpGenerator():
    def __init__(self):
        self._awcs = {}
        self._scripts = {}
        self._sounds = {}
        self._scripts = {}

        self._parsed_hashes = set()

    def add_hasher(self, hasher):
        self._hasher = hasher

    def _add_items(self, target, base):
        for key, value in base.items():
            if key in target:
                # happens somewhat commonly and objects have differences, but main info (links) seems the same
                #print("repeat: hash %08x type %x" % (value.hash, value.type))
                #raise ValueError(f"Duplicate key found: {key}")
                pass
            target[key] = value

    def add_awc(self, awc):
        name = rtxtp.get_awc_key(awc.filename)

        # BOB_MP_RACE_BAYOU exists 2 paths
        if name in self._awcs:
            #raise RuntimeError("repeated awc name", name)
            print("repeated awc name:", name)

        self._awcs[name] = awc #.streams
        #self._awcs[os.path.basename(name)] = awc #.streams

    def add_rel(self, rel):
        self._add_items(self._scripts, rel.scripts)
        self._add_items(self._sounds, rel.sounds)

    #--------------------------------------------------------------------------

    def _detect_unreferenced_awc(self):
        # find refs to .awc in sounds
        used_awc = set()
        for obj in self._sounds.values():
            if obj.type != 0x0c:
                continue
            
            hname = self._hasher.get(obj.awc, awc_hash=True)
            if hname:
                awc_name = hname.upper()
                awc_name = os.path.basename(awc_name)
            else:
                awc_name = "0x%08X" % (obj.awc)

            #awc_base = os.path.basename(awc_name)
            #if awc_name not in self._awcs and awc_base not in self._awcs:
            #    continue
            if awc_name not in self._awcs:
                continue
            
            used_awc.add(awc_name)
            #used_awc.add(awc_base)
            #print("0x%08x: %s" % (obj.awc, awc_name))


        # find if loaded .awc are unused in sounds (happens in rare cases)
        for awc in self._awcs:
            if awc not in used_awc:
                print("Loaded AWC not found in .rel: " + awc)
                #raise ValueError("Loaded AWC not found in .rel: " + awc)


    #--------------------------------------------------------------------------

    def _get_obj(self, hash, items, types=None):
        if not hash or hash < 0 or hash == 0xFFFFFFFF:
            return None
        self._parsed_hashes.add(hash)

        obj = items.get(hash)
        if not obj:
            print("child %08x not found (load more .rel?)" % (hash)) #debug stuff? (doesn't seem to exist)
            return None

        if types and obj.type not in types:
            raise ValueError("unexpected type %08x" % (hash))
        return obj

    # completes TxtpInfo from recursive calls to sound objects
    def read_track(self, hash, track):
        obj = self._get_obj(hash, self._sounds)
        if not obj:
            return None

        if obj.type in [0x08, 0x0D]: #StreamingSound/SimpleSound, info ordered
            for subhash in obj.sounds:
                self.read_track(subhash, track)

        if obj.type in [0x0C]: #SimpleSound leaf
            track.add_awc(obj.awc)
            track.add_channel(obj.channel) #names are just _LEFT/RIGHT suffixes so no need to add
    
    def get_track(self, hash):
        track = rtxtp.TxtpTrack(self._hasher)
        self.read_track(hash, track)
        return track

    def get_stem(self, hash):
        obj = self._get_obj(hash, self._scripts, [0x44])
        if not obj:
            return None

        return obj.volumes

    def get_mood(self, hash):
        obj = self._get_obj(hash, self._scripts, [0x49])
        if not obj:
            return []
        
        # a mood has N stems (maybe linked?) but here are treated separately
        # it also may have another mood
        volumes = []
        if obj.mood:
            stems = self.get_mood(obj.mood)
            for stem in stems:
                if stem in volumes:
                    continue
                volumes.append(stem)

        for subhash in obj.stems:
            stem = self.get_stem(subhash)
            if not stem:
                continue
            if stem in volumes:
                continue
            volumes.append(stem)
        return volumes

    def register_event(self, prev_track, event):
        num_layers = len(prev_track.channels) // 2

        # some fake events don't make sense since they can't mod current track
        # for example BOB_WINTER_4_SONG_2 (WNT4_START) has 2 channels, so any WNT4_* with volumes after 2 can be ignored
        if event.unconfirmed and event.stem:
            if all(vol <= -10000 for vol in event.stem):
                return

            for i, volume in enumerate(event.stem):
                if volume > -10000 and i >= num_layers:
                    return

        # add current events to prev track
        is_new_event = True
        for prev_event in prev_track.events:
            # event with same stem = copy names
            if event.stem == prev_event.stem or event.unconfirmed and prev_event.stem is None and num_layers == 1:
                is_new_event = False
                prev_event.add_names(event.names)

        if is_new_event:
            prev_track.add_event(event)

    def register_track(self, track):
        if not track.awc:
            #print("track with randoms")
            #track.print()
            return

        prev_track = self._tracks_done.get(track.awc)

        # not seen
        if prev_track and len(prev_track.channels) != len(track.channels):
            raise ValueError("track with channel diffs")


        # new track
        if not prev_track:
            self._tracks.append(track)
            self._tracks_done[track.awc] = track
            return

        # add current events to prev track
        for event in track.events:
            self.register_event(prev_track, event)

    def count_matching_chars(self, str1, str2):
        count = 0
        for char1, char2 in zip(str1, str2):
            if char1 != char2:
                break
            count += 1
        return count

    def has_matching_names(self, track, name):
        for prev_event in track.events:
            for prev_name in prev_event.names:
                count = self.count_matching_chars(name, prev_name)
                if count >= 4:
                    return True
        return False

    def register_unconfirmed_event(self, event):
        # add current name + volumes to existing tracks
        #print("event:" , event.names)
        
        if all(name.startswith('0x') for name in event.names):
            return
        
        for name in event.names:
            if name.startswith('0x'):
                continue

            part = name.split('_')[0]
            tracks = self._namepart_to_tracks.get(part, [])
            for track in tracks:
                if self.has_matching_names(track, name):
                    self.register_event(track, event)


    def register_nameparts(self):
        # WNT1 > track
        self._namepart_to_tracks = {}

        for track in self._tracks:
            for event in track.events:
                if event.oneshot:
                    continue
                for name in event.names:
                    if name.startswith('0x'):
                        continue
                    part = name.split('_')[0]
                    if part not in self._namepart_to_tracks:
                        self._namepart_to_tracks[part] = set()
                    self._namepart_to_tracks[part].add(track)


    def _include_extra_moods(self):
        self.register_nameparts()

        # detect extra moods that don't have an associated sound (meant to be triggered after some .awc is loaded)
        print('detecting extra moods')
        for hash in self._scripts:
            if hash in self._parsed_hashes:
                continue
            obj = self._scripts[hash]
            stems = []
            if obj.type in [0x4c]: #SetMoodAction
                stems = self.get_mood(obj.mood)

            if obj.type in [0x49]: #InteractiveMusicMood
                stems = self.get_mood(obj.mood)
                if obj.stems: #todo detect
                    for stem_hash in obj.stems:
                        stem = self.get_stem(stem_hash)
                        stems.append(stem)

            if not stems:
                continue

            for stem in stems:
                event = rtxtp.TxtpEvents(self._hasher)
                event.add_name(obj.hash)
                event.put_stem(stem)
                event.unconfirmed = True

                self.register_unconfirmed_event(event)


    def _include_missing_moods(self):
        print('including missing moods')
        for track in self._tracks:
            num_layers = len(track.channels) // 2

            if num_layers == 1:
                continue
            if all(event.oneshot for event in track.events):
                continue

            #extra_volumes = [0] * (len(track.channels) // 2)
            extra_volumes = [0] * 16
            for i in range(len(track.channels) // 2, len(extra_volumes)):
                extra_volumes[i] = -10000

            # mark volumes silent based on existing events
            for event in track.events:
                if not event.stem or event.oneshot:
                    continue
                for i, volume in enumerate(event.stem):
                    #layer used elsewhere = mark current as silent
                    if volume > -10000:
                        extra_volumes[i] = -10000

            
            if not any(vol > -10000 for vol in extra_volumes[0:num_layers]):
                continue

            # if some of the layers weren't used add extra layers
            event = rtxtp.TxtpEvents(self._hasher)
            event.add_name_str('extra')
            event.put_stem(extra_volumes)
            event.unconfirmed = True

            #self.register_unconfirmed_event(event)
            track.add_event(event)


    def _find_events(self):
        # handle good events
        print('finding events')
        for hash in self._scripts:
            obj = self._scripts[hash]
            #if obj.type not in [0x52, 0x4a, 0x4e]:
            #    continue
            
            if obj.type == 0x52: #StartOneShotAction
                # basic txtp without mood
                event = rtxtp.TxtpEvents(self._hasher)
                event.add_name(obj.hash)
                event.set_oneshot() #no loop

                track = self.get_track(obj.sound)
                track.add_event(event)

                self.register_track(track)

            if obj.type == 0x4a: #StartTrackAction
                if obj.sound and obj.sounds: #rare (0xac0a1eea)
                    print("multisound found in 0x%08x" % (obj.hash))
                    #raise ValueError("multisound found in 0x%08x" % (obj.hash))

                # sound with mood aplied:
                if obj.sound:
                    stems = self.get_mood(obj.mood)

                    for stem in stems:
                        event = rtxtp.TxtpEvents(self._hasher)
                        event.add_name(obj.hash)
                        event.add_name(obj.mood)
                        event.put_stem(stem)

                        track = self.get_track(obj.sound)
                        track.add_event(event)

                        self.register_track(track)

                # rare, for N related sounds but all seem to be a single track (no mood?)
                if obj.sounds:
                    for sound in obj.sounds:
                        event = rtxtp.TxtpEvents(self._hasher)
                        event.add_name(obj.hash)

                        track = self.get_track(sound)
                        track.add_event(event)

                        self.register_track(track)


    def _make_txtp_lines(self):
        self._tracks_done = {} #awc > track
        self._tracks = []

        self._find_events()
        self._include_extra_moods()
        self._include_missing_moods()

        # make a txtp line in this format:
        #   (path)/file.awc (commands) : (final-name).txtp
        # which can be used with txtp-dumper.py
        #
        # Doesn't make .txtp directly as some variations are created by mood actions and can't autogenerated,
        # so this list can be filled with missing variations by checking mood names
        print('printing txtp list')
        formatter = rtxtp.TxtpFormatter()
        lines = []
        tracks = sorted(self._tracks, key=lambda x: x.awc)
        for track in tracks:
            if not track.events:
                raise ValueError("awc with no events: %s" % (track.awc))

            file_info = track.awc
            file_cmd = formatter.track_to_basefile(track)
            remap_cmd = formatter.track_to_remap(track, self._awcs)

            #events = sorted(track.events, key=lambda x: x.stem if x.stem is not None else [])
            events = track.events
            for event in events:
                loop_cmd = formatter.event_to_loop(event)
                event_txt = formatter.event_to_comment(event)
                event_info = formatter.event_to_info(event)
                if len(event_info) > 50:
                    event_info = event_info[0:50] + '...'
                if event_info:
                    mark = ''
                    if event.unconfirmed:
                        mark = '~'
                    event_info = f' ({mark}{event_info})'

                # main txtp per stem
                stem_cmd = formatter.stem_to_commands(event.stem)

                stem_info = formatter.stem_to_info(event.stem)
                if stem_info:
                    stem_info = f' [{stem_info}]'

                base_dir = TXTP_BASE
                if track.awc.startswith('dlc') or track.awc.startswith('patch'):
                    base_dir += 'dlcpacks/'
                else:
                    base_dir += 'audio/'

                external_name = f'{base_dir}{file_info}{stem_info}{event_info}.txtp'

                internal_txtp = f'{file_cmd}{loop_cmd}{remap_cmd}{stem_cmd}'
                if len(track.channels) != 2:
                        internal_txtp += ' #@layer-e 2'

                line = f'{external_name:115} : {internal_txtp}'
                if event_txt:
                    line += f' \\n## {event_txt}'
                if event.unconfirmed:
                    line += f' \\n## (unconfirmed mood)'
                    #line = '#' + line
                if event.oneshot or '#v ' in stem_cmd or len(track.channels) <= 2:
                    line = '#' + line
                #if not event.oneshot and len(track.channels) <= 2:
                #    line = '#!' + line
                lines.append(line)
        
        #lines.sort()
        outfile = 'txtp-list.txt'
        with open(outfile, 'w') as f:
            f.write('\n'.join(lines))

    def start(self):
        print('generating TXTP')

        rgenerator_tree.TxtpGeneratorTree(self).print_tree()

        self._detect_unreferenced_awc()
        self._make_txtp_lines()
