# little printer thing that grew up and became wwiser (https://github.com/bnnm/wwiser)
# useless but kept for fun

#!/usr/bin/env python3

import os
import sys
import glob
import argparse
import re
import json
import struct

#http://wiki.xentax.com/index.php/Wwise_SoundBank_(*.bnk)#type_.231:_Settings
#known versions
# 0x70: Transformers
# 0x71: Nier Automata
# 0x80: Spyro Trilogy
# 0x84: Astral Chain
# 0x86: Wwise 2019.1.3.7048

object_type_names = {
    0x01: "Settings",
    0x02: "Sound SFX/Voice",
    0x03: "Event Action",
    0x04: "Event Sequence",
	0x05: "Random/Sequence Container",
	0x06: "Switch Container",
	0x07: "Actor-Mixer",
    0x08: "Audio Bus",
    0x09: "Blend Container",
    0x0a: "Music Segment",
    0x0b: "Music Track",
    0x0c: "Music Switch Container",
    0x0d: "Music Playlist Container",
    0x0e: "Attenuation",
    0x0f: "Dialogue Event",
    0x10: "Motion Bus",
    0x11: "Motion FX",
    0x12: "Effect",
    0x13: "Auxiliary Bus",
}
soundsfx_mode_names = {
    0x00: "Bank",
    0x01: "Stream",
    0x02: "Prefetch",
}

event_scope_names = {
    0x01: "Game object by Switch/Trigger",
    0x02: "Global",
    0x03: "Game object by refid",
    0x04: "Game object by State",
    0x05: "All",
    0x09: "All except refid",
}
event_action_names = {
    0x01: "Stop",
    0x02: "Pause",
    0x03: "Resume",
    0x04: "Play",
    0x05: "Trigger",
    0x06: "Mute",
    0x07: "UnMute",
    0x08: "Set Voice Pitch",
    0x09: "Reset Voice Pitch",
    0x0A: "Set Voice Volume",
    0x0B: "Reset Voice Volume",
    0x0C: "Set Bus Volume",
    0x0D: "Reset Bus Volume",
    0x0E: "Set Voice Low-pass Filter",
    0x0F: "Reset Voice Low-pass Filter",
    0x10: "Enable State",
    0x11: "Disable State",
    0x12: "Set State",
    0x13: "Set Game Parameter",
    0x14: "Reset Game Parameter",
    0x19: "Set Switch",
    0x1A: "Enable/Disable Bypass",
    0x1B: "Reset Bypass Effect",
    0x1C: "Break",
    0x1E: "Seek",
}


def get_name(table, id):
    if id in table:
        return table[id]
    else:
        return "unknown"


class FileReader(object):
    def __init__(self, file):
       self.file = file
       self.offset = 0
       self.be = False

    #def _read_buf(self, offset, type, size):
    #    elem = self.buf[offset:offset+size]
    #    return struct.unpack(type, elem)[0]
    #
    
    def _read(self, offset, type, size):
        if offset is not None:
            self.file.seek(offset, 0)
        elem = self.file.read(size)
        return struct.unpack(type, elem)[0]

    def _read_string(self, offset, size):
        if offset is not None:
            self.file.seek(offset, 0)
        elem = self.file.read(size)
        return elem.split('\0', 1)[0]

    def u32le(self, offset = None):
        return self._read(offset, '<I', 4)

    def u32be(self, offset = None):
        return self._read(offset, '>I', 4)

    def u16le(self, offset = None):
        return self._read(offset, '<H', 2)

    def u16be(self, offset = None):
        return self._read(offset, '>H', 2)

    def u32(self, offset = None):
        if self.be:
            return self.u32be(offset)
        else:
            return self.u32le(offset)

    def u16(self, offset = None):
        if self.be:
            return self.u16be(offset)
        else:
            return self.u16le(offset)

    def s8(self, offset = None):
        return self._read(offset, 'b', 1)
            
    def u8(self, offset = None):
        return self._read(offset, 'B', 1)

    def str(self, size, offset = None):
        return self._read_string(offset, size)

    def seek(self, offset):
        self.file.seek(offset, 0)

    def skip(self, bytes):
        self.file.seek(bytes, 1)

    def current(self):
        return self.file.tell()

    def guess_endian32(self, offset):
        current = self.file.tell()
        var_le = self.u32le(offset)
        var_be = self.u32be(offset)
        
        if var_le > var_be:
            self.be = True
        else:
            self.be = False
        self.file.seek(current)
        
    def set_endian(self, big_endian):
        self.be = big_endian

def parse():
    description = (
        "prints wwise .bnk info"
    )
    epilog = (
        "examples:\n"
        "  %(prog) *.bnk\n"
    )

    parser = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("files", help="files to get (wildcards work)")
    return parser.parse_args()


def is_file_ok(args, glob_file):
    if not os.path.isfile(glob_file):
        return False
        
    if glob_file.endswith(".py"):
        return False
    return True
    
class WwiseObject:
    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__,  sort_keys=False, indent=4)
    def __repr__(self):
        return self.toJson()


#def parse_sound(r):



def parse_main(r, size):
    r.guess_endian32(0x04)
    offset = 0

    bkhd = WwiseObject()


    while offset < size:
        r.seek(offset)
        chunk_id   = r.u32be()
        chunk_size = r.u32()
        
        if chunk_id == 0x424B4844: #BKHD
            bkhd.version = r.u32()
            bkhd.id = r.u32()
            bkhd.unknown1 = r.u32()
            bkhd.unknown2 = r.u32()
            bkhd.unknown3 = r.u32()
            
            print("BHNK chunk:")
            print(" version: %i\n"
                  " id: %i\n"
                  " unk1: 0x%x\n"
                  " unk2: 0x%x\n"
                  " unk3: 0x%x"
                  % (bkhd.version, bkhd.id, bkhd.unknown1, bkhd.unknown2, bkhd.unknown3))
        
        elif chunk_id == 0x44494458: #DIDX
            print("DIDX chunk")
            print("(...)")

        elif chunk_id == 0x53544d47: #STMG
            print("STMG chunk")
            
            stmg_unk1 = r.u32()
            stmg_unk2 = r.u32()
            stmg_unk3_count = r.u32()
            
            print(" unk1: 0x%x\n"
                  " unk2: 0x%x\n"
                  " unk3 count: %i"
                  % (stmg_unk1, stmg_unk2, stmg_unk3_count))

            for i in range(0, stmg_unk3_count):
                current = r.current()
                unk3_id = r.u32()
                unk3_unk1 = r.u32()
                unk3_unk2 = r.u32()

                print(" unk3[%i] at 0x%x:\n"
                      "  id: %i\n"
                      "  unk1: %i\n"
                      "  unk2: 0x%x"
                      % (i, current,
                        unk3_id, unk3_unk1, unk3_unk2))

                print("")

            print("(...)")

            
            
        elif chunk_id == 0x48495243: #HIRC
            print("HIRC chunk")

            object_count = r.u32()
            #print(" object count: %i" % (object_count))
            
            for i in range(0, object_count):
                current = r.current()
                print(" object[%i] at 0x%x:" % (i, r.current()))
                o_type = r.u8()
                o_size = r.u32()
                o_id = r.u32()
                
                print("  type: 0x%02x-%s\n"
                      "  size: 0x%x\n"
                      "  id: %i"
                      % (o_type, get_name(object_type_names, o_type), 
                         o_size, 
                         o_id))

                if   o_type == 0x02: #sound sfx
                    ss_unk1 = r.u32()
                    ss_mode = r.u8()
                    ss_refid = r.u32()
                    ss_unkid = r.u32()

                    print("  mode: %s\n"
                          "  refid: %i\n"
                          "  unkid: %i"
                          % (get_name(soundsfx_mode_names , ss_mode), 
                            ss_refid, 
                            ss_unkid))
                    print("  (...)")

                elif   o_type == 0x03: #event action
                    ea_scope = r.u8()
                    ea_action = r.u8()
                    ea_refid = r.u32()

                    print("  scope: 0x%02x-%s\n"
                          "  action: 0x%02x-%s\n"
                          "  refid: %i"
                          % (ea_scope, get_name(event_scope_names, ea_scope), 
                            ea_action, get_name(event_action_names, ea_action), 
                            ea_refid))
                    print("  (parameters, states, switches...)")
                    

                elif o_type == 0x04: #event sequence
                    es_count = r.u8()
                    #print(" sequence count: %i" % (es_count))

                    for i in range(0, es_count):
                        print("  event action[%i] at 0x%x:" % (i, r.current()))
                        print("   refid: %i" % r.u32())

                else:
                    print("  (...)")

                print("")
                r.seek(current + 0x01+0x04 + o_size) # no need to parse fully
            
        elif chunk_id == 0x44415441: #DATA
            print("DATA chunk")
            print("(...)")

        elif chunk_id == 0x494E4954: #INIT
            print("INIT chunk")

            init_count = r.u32()
            print(" init count: %i" % (init_count))

            for i in range(0, init_count):
                current = r.current()
                init_unk1 = r.u16()
                init_unk2 = r.u16()
                init_nsize = r.u32()
                init_name = r.str(init_nsize)
                print("  init[%i] at 0x%x: 0x%04x 0x%04x %s"
                      % (i, current, init_unk1, init_unk2, init_name))

        elif chunk_id == 0x454E5653: #ENVS
            print("ENVS chunk")
            print("(...)")

        elif chunk_id == 0x504C4154: #PLAT
            print("PLAT chunk:")
            plat_nsize = r.u32()
            plat_name = r.str(plat_nsize)
            print(" platform: %s" % (plat_name))

        else:
            print("%x chunk" % (chunk_id))

        print("")

        offset += 0x08 + chunk_size

def main(): 
    args = parse()

    # get target files
    glob_files = glob.glob(args.files)
    
   
    files = []
    for glob_file in glob_files:
        if not is_file_ok(args, glob_file):
            continue
        print("printing " + glob_file + ":")
        
        with open(glob_file, 'rb') as infile:
            size = os.path.getsize(infile.name)
            r = FileReader(infile)
            parse_main(r, size)
            

if __name__ == "__main__":
    main()
   
