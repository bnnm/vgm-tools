import rprinter, rdefs


class TxtpGeneratorTree():
    def __init__(self, generator):
        self.generator = generator



    def _add_objinfo(self, obj, printer, types):
        gen = self.generator

        hname = gen._hasher.get(obj.hash)
        description = types.get(obj.type, '?')
        info = "0x%08X: %02x [%s] %s" % (obj.hash, obj.type, description, hname)
        printer.add(info)


    def _print_sound(self, hash, printer):
        gen = self.generator

        if not hash or hash < 0 or hash == 0xFFFFFFFF:
            return
        obj = gen._sounds.get(hash)
        if not obj:
            printer.add("child %08x not found" % (hash))
            return

        self._add_objinfo(obj, printer, rdefs.REL98_SOUND_TYPES)
        printer.next()

        if obj.type in [0x08, 0x0D]:
            for subhash in obj.sounds:
                self._print_sound(subhash, printer)

        if obj.type in [0x0C]:
            printer.add("awc 0x%08X %s" % (obj.awc, gen._hasher.get(obj.awc, awc_hash=True)))
            printer.add("chn 0x%08X %s" % (obj.channel, gen._hasher.get(obj.channel, awc_hash=True)))

        ## todo handle randoms? they may call to N Tracks but there are only a few for events

        printer.prev()


    def _print_script(self, hash, printer):
        gen = self.generator

        if not hash or hash < 0 or hash == 0xFFFFFFFF:
            return
        obj = gen._scripts.get(hash)
        if not obj:
            printer.add("child %08x not found" % (hash))
            return

        self._add_objinfo(obj, printer, rdefs.REL325_SCRIPT_TYPES)
        printer.next()

        if obj.type in [0x52]: #StartOneShotAction
            self._print_sound(obj.sound, printer)

        if obj.type in [0x4e]: #StartActionList
            for action in obj.actions:
                self._print_script(action, printer)

        if obj.type in [0x4a]: #StartTrackAction
            self._print_script(obj.mood, printer)
            self._print_script(obj.stem_f32, printer)
            self._print_sound(obj.sound, printer)
            printer.next()
            for sound in obj.sounds:
                self._print_sound(sound, printer)
            printer.prev()

        if obj.type in [0x4c]: #SetMoodAction
            self._print_script(obj.mood, printer)
            self._print_script(obj.stem_f32a, printer)
            self._print_script(obj.stem_f32b, printer)

        if obj.type in [0x49]: #InteractiveMusicMood
            self._print_script(obj.mood, printer)
            printer.next()
            for stem in obj.stems:
                self._print_script(stem, printer)
            printer.prev()

        if obj.type in [0x44, 0x46]: #StemMix / StemMixFloat
            printer.add(obj.volumes)

        printer.prev()

    def print_tree(self):
        gen = self.generator
        
        # TODO 08 > 0D > 0C to make TXTP
        printer = rprinter.RagePrinter()
        for hash in gen._scripts:
            obj = gen._scripts[hash]
            if obj.type not in [0x52, 0x4a, 0x4e, 0x49, 0x4c]: #some 49/4c aren't called by events
                continue
            self._print_script(hash, printer)
            printer.add('')
        printer.save("tree.txt")
