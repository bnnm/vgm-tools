# RAGETOOL

- `ragetool.pyz -r rel/**/*.dat325.rel rel/**/*.dat98.rel awc/**/*.awc  -d -sl`
  - dumps .rel and .awc info to simple .txt (for debugging purposes)
- `ragetool.pyz -r rel/**/*.dat325.rel rel/**/*.dat98.rel -sl`
  - saves a list of reversable hases (not every name is included since some aren't useful for audio)
- `ragetool.pyz -r rel/**/*.dat325.rel rel/**/*.dat98.rel awc/**/*.awc  -g`
  - creates a .txtp list


# RDR2 RAGE ENGINE AUDIO STUFF (by bnnm)

The way RDR2's dynamic music works is similar to Wwise but with extra challenges. More or less it goes like this:
- engine reads various .rel files with sound info
  - found in audio_rel.rpf as well as update.rpf and other dlc packs in `/x64/audio/config`
  - roughly, .dat325.rel define audio events and .dat98.rel define audio objects
- game scripts call some audio event (StartTrackAction)
- events may define a "mood" (InteractiveMusicMood) of "stems" (StemMix) = layer volumes + audio object
  - events have extra stuff such as fade times and so on
  - some events have multiple moods, probably meant to be played for some seconds then change in order
- typical audio object (StreamingSound) defines all layers (MultitrackSound) of 2 channels (SimpleSound) from some .awc
  - note that .awc channels as found in .awc are *not* ordered and the correct order is the above
- combined we have base event + layer volumes + multi-layer awc = dynamic music

Non-dynamic music works the same but there are other sound types like randoms, wrappers and stuff where moods and layers/MultitrackSound aren't used.

We could use .rel info to make .txtp with layers (similar to wwiser). However the way events are defined makes it harder:
- usually a base "start" event loads one audio object (ultimately some .awc) + sets first layer "mood"
  - there are few "restart" (checkpoint?) events like that too
- *however* some events only change moods (layers) but don't define any audio object
  - in other words we don't know when/why it's used
  - probably can be used with with any loaded .awc so testing themis not useful
    - Rampage mod can manually call events
- would need to check scripts or reverse the names and see if base event (.awc loader) and mood events are named similarly
- event's names are hashes (jooat) but can be reversed similar to wwise (see below)

To handle all that I made `ragetool.pyz`, that can read rdr2 .rel and dump them to .txt (only for events and sounds), or generate `.txtp`. It's kinda unsightly but whatevs.

## COMPATIBILITY
This only works for RDR2.

Audio seems to work the same in other Rockstar games, but .rel format changes a bit between games.

For example GTA4 has `SOUNDS.DAT15`, GTA5 has `sounds.dat54.rel` and `game.dat151.rel`. Other tools can read those rels:
- https://github.com/dexyfex/CodeWalker
- https://github.com/Parik27/GTAAudioMetadataTool/
- https://github.com/AndrewMulti/RAGE-Audio-Toolkit


## TXTP GENERATION
`ragetool.pyz -g -r rel/**/*.dat325.rel rel/**/*.dat98.rel awc/**/*.awc`
- put `rnames.txt` with the toor
- read all .rel
  - make you sure to have .rel from update4.rpf and extra stuff (mp*/dlc*/patch*.rpf)
- read all .awc
  - needed to know where are their channels and remap layers correctly
- dumps a tree.txt
  - this is for reference to easier comparison
- dumps txtp-list.txtp
  - this can be used with txtp_dumper.py to create actual .txtp, copied near `.awc`. 

It's saved like a list since not all .txtp are "confirmed" and the file is meant to be tweaked.

Since some events set moods without defined .awc, the tool tries to match them to some .awc by using their reversed name and some other tricks. .txtp with "~" in the name are probably ok but unconfirmed. We don't have every reversed name so some layers combos are missing (those are "unknown" layers are marked as "extra").

TXTP names include events that use them but some .awc are used by multiple events, so names are kinda messy. Thus it's mostly meant to be tweaked manually.

Oneshots are commented out since their .txtp isn't useful (no layers) though their event name is good to figure out where they play. Same for events that set silence *mood* (often done at the beginning of a missions).


# REVERSING NAMES
Base names come from resources by other folks (see below) but since many audio-related names weren't known I added a decent bunch myself (see `rrnames.txt` in related dirs).

To reverse: blah blah see wwiser-utils' `words.py` and related docs. For Rockstar's hash I made rwords.py that works the same:
```
ragetool.pyz -r rel/**/*.dat325.rel rel/**/*.dat98.rel -d -sl

rwords.pyz (flags)
```
That dumps .rel to .txt (optional) and creates `rnames-(date).txt` list with missing hashes. With some creativity and rwords.py many event names can be found.

Some RAGE files have event names too: `\x64\levels\rdr3\script\parseddata.rpf` (main or update_2.rpf) but not all of them.


# RESOURCES
- https://github.com/OpenIV-Team/RAGE-StringsDatabase/
- https://github.com/femga/rdr3_discoveries/tree/master/audio
- https://github.com/dexyfex/CodeWalker
- https://github.com/CamxxCore/RageAudioTool
- https://github.com/Monkeypolice188/Monkys-Audio-Research
- https://github.com/cpmodding/Codex.Games.RDR2.strings
- https://github.com/kepmehz/RDR3-Decompiled-Scripts
- https://github.com/stianhje/rdr3-decompiled-scripts.1232
- https://github.com/CamxxCore/RageAudioTool
- https://www.nexusmods.com/reddeadredemption2/mods/233
- OpenIV


# EVENT EXAMPLES

## EVENT EXAMPLE 1
- in the mission *Red Dead Redemption* (finale1) there are 2 variations of the song that plays when riding back to camp
- `FIN1_CAMP_RIDE_HIGH` plays *mood* `SM_1` (high honor variation)
- `FIN1_CAMP_RIDE_LOW` plays *mood* `SM_2` (low honor variation)
```
0xCFCCFA4B: 4a [StartTrackAction] FIN1_CAMP_RIDE_HIGH
  0x0157AC95: 49 [InteractiveMusicMood] FIN1_CAMP_RIDE_HIGH_MD
      0x8DF4DCF7: 44 [StemMix] SM_1
        [0, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000]
  0x07583878: 08 [StreamingSound] 
    0xDA27A30A: 0d [MultitrackSound] 
      0x6750D438: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0x0DB8BFE2 BOB_THATSTHEWAYITIS_1_LEFT
      0x2A2CC4FE: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0xCB29DCB0 BOB_THATSTHEWAYITIS_1_RIGHT
    0x80CC5F7E: 0d [MultitrackSound] 
      0xEC3D5C1C: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0xB900E609 BOB_THATSTHEWAYITIS_2_LEFT
      0xD982E572: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0x1EC5E3F6 BOB_THATSTHEWAYITIS_2_RIGHT

0x792BCEB5: 4a [StartTrackAction] FIN1_CAMP_RIDE_LOW
  0xD18ED5D3: 49 [InteractiveMusicMood] FIN1_CAMP_RIDE_LOW_MD
      0x7B993840: 44 [StemMix] SM_2
        [-10000, 0, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000, -10000]
  0x07583878: 08 [StreamingSound] 
    0xDA27A30A: 0d [MultitrackSound] 
      0x6750D438: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0x0DB8BFE2 BOB_THATSTHEWAYITIS_1_LEFT
      0x2A2CC4FE: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0xCB29DCB0 BOB_THATSTHEWAYITIS_1_RIGHT
    0x80CC5F7E: 0d [MultitrackSound] 
      0xEC3D5C1C: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0xB900E609 BOB_THATSTHEWAYITIS_2_LEFT
      0xD982E572: 0c [SimpleSound] 
        awc 0x34EB3AB5 SCORE_05/BOB_THATTHEWAYITIS
        chn 0x1EC5E3F6 BOB_THATSTHEWAYITIS_2_RIGHT
```

## EVENT EXAMPLE 2
- in the mission *The Sheep and the Goats* (mudtown4) is made of 2 parts, one the overworld with John and one in Valentine
- `MUD4_START_STA` sets mood `SM_SILENCE` and loads `BOB_29_AMB_OW.awc`
  - there is no txtp for this since it's silent
- another event `MUD4_RIDE_MIX` with `SM_1` which is probably used during conversations
  - there is a txtp for this, which includes some other similar names
- there are a bunch of events that swap moods during the mission, controlled by complex scripts (outside what this tool 'sees')
- then when entering Valentine it calls `MUD4_BAR_2` with mood `SM_11` that loads `BOB_MUDTOWN_4.awc` (tension track)
- then it calls `MUD4_PUSH_CART` with moods `SM_3_4_5_9` > `SM_3_4_5_6_9` > `SM_3_4_5_6_7_8_9_10` > `SM_2_3_4_5_6_7_8_9_10`
  - those moods seem to last a set time making a full track, see dat325.rel for full info, but tool simply makes 1 txtp per mood
- HOWEVER! `MUD4_PUSH_CART` doesn't have an associated `.awc`, just loads moods
- this means you could use it with `BOB_29_AMB_OW.awc` and `BOB_MUDTOWN_4.awc`, but in reality it's used for the later
- since tool can't autodetect where it's used, it assumes it could go to both and creates:
  - `BOB_29_AMB_OW [SM_3_4_5_6_9] (~MUD4_PUSH_CART)`
  - `BOB_MUDTOWN_4 [SM_3_4_5_6_9] (~MUD4_PUSH_CART)`
  - detection is based on events named like `MUD4`
- in other words: must manually delete `BOB_29_AMB_OW [SM_3_4_5_6_9] (~MUD4_PUSH_CART)` and leave the other


# INTERNAL STUFF

## MAIN SOUNDS TYPES:
- .dat98.rel defines audio objects (regular, randoms, etc):
  - `08 [StreamingSound] > 0d [MultitrackSound] > 0c [SimpleSound]`
  - `08 [StreamingSound] > 0c [SimpleSound]`
  - `06 [WrapperSound] > 08 [StreamingSound] / 0e [RandomizedSound] / etc > ...`
- 08 defines a list of streams in .awc, either layers or N simple sounds (all at once, silenced by events)
  - stream order here is the proper one to play .awc
- 0d defines a stereo layer for interactive music
- 0c defines a part of an .awc

```
08 [StreamingSound] //.awc
    sounds []

0d [MultitrackSound] //stereo(?) track
    sounds []

0c [SimpleSound] //.awc subsong
    awc
    channel
```
## MAIN OBJECT TYPES:
 - .dat325.rel defines music events:
   - 4a [StartTrackAction] > 08 [StreamingSound] + 49 [InteractiveMusicMood] > 44 [StemMix]
   - 52 [StartOneShotAction] > ...
 - 4a plays some sound + sets layers's volume via mood/stemmix
   - some tracks are silenced with 4c [SetMoodAction] sometimes called with 4e [StartActionList?], once track is loaded
     - (meaning some stem variations don't exist outside manual silencing of tracks)
- 49 lists N stems (config by time?)

```
52 [StartOneShotAction]
    sound

4e [StartActionList?]
    actions []

4a [StartTrackAction]
    sound
    mood
    stem_f32
    sounds []

4c [SetMoodAction]
    mood
    stem_f32a
    stem_f32b

49 [InteractiveMusicMood]
    mood
    stems []

44 [StemMix]
    volumes

46 [StemMixFloat]
    volumes

```