# RETAGGER - TAGSM3U AUTOMAKER
#
# Compares similar files from a 'tagged' folder vs an 'untagged' folder and makes a !tags.m3u for matches cases.
# Files can be of any format that vgmstream supports (even .flac or .mp3). Accuracy is pretty ok, it's a bit slow.
#
# For renamed files (like '01 Artist - Title.adx' <> 'BGM01.adx') better use filetags-to-tagsm3u.py instead.
#
# Usage:
# - install dependencies (see below)
# - make a 'tagged' folder and copy a tagged .flac/.ogg/.mp3 gamerip (or even an OST), subfolders are ok
# - make a 'untagged' folder and copy streamed files, subfolders are ok too
# - run this tool (may need to tweak params from the command line)
#   - by default loads all audio from tagged/untagged, you may need to specify -fu to limit to .txtp/etc in untagged
#   - '-dv 3 -q -m euc' is a good starting point for gamerips to test a bit
# - after done (will take a while) it should make !tags.m3u in the untagged folder(s)
#   - if it's taking too long try using -q for quicker but less accurate results (or go make a sandwich)
# - open !tags.m3u in a player and text editor and check for errors
#   - see below for common issues
#
# OST files are often mastered differently and matching is less accurate (need more tweaking).
# This tool works better when all files are present in both folders. If your gamerip/OST lacks
# DLC songs, they will probably end up being be misidentified unless you use some aggresive
# -t N value. It's best to put them in some subfolder so they are easier to fix.
#
#
# Params that may or may not help:
# -dv N: max deviation of time between files to consider them the same (in seconds, ~3 is probably good).
#       Very useful with gamerips made with vgmstream's defaults (2 loops, 10s fade) AKA most of them,
#       plus cuts down time a lot. Mostly useless with OSTs.
# -dl N: number of loops used for -dv, useful for some gamerips that only loop once. 0 disables looping in calcs.
# -df N: fade time, same as above
# -mo: matches each tagged file only once. By default it matches multiples times since it's not uncommon to have
#      multiple variations of the same file, but sometimes makes odd matches without fine-tuned '-t N'. It's
#      probably easier/better to try '-mo' before fiddling with '-t N'.
# -q: simplifies some calculations to speed up processing, at the cost of accuracy. 
#     Combine with '-m euc' for much faster methods (and '-dv N' too).
# -t N: threshold or minimum accuracy % to accept files (lower allows worse matches).
#       By default it's auto-calculated based on results, tweak manually if too many false positives.
#       Lower it if files are somewhat different but still similar (such as extended intros).
# -s N: tests more seconds, slightly increases accuracy but is slower. 15-30s is usually good enough.
#       If your game has many files that start the same but change after a while you may need more seconds.
# -tis: prints scores in !tags.m3u to help identify wrong matches.
# -r N: resample value. Files are resampled before comparing but default is usually best.
#       High or low values may decrease accuracy for files of different qualities.
#
# The tool can't be perfect so you may need to manually tweak !tags.m3u, for example:
# - files and tags that didn't match anything are printed at the bottom of the list
# - small variations (normal, quieter) may be detected as the same base song
# - files with no matching tag (not part of original rip/OST) may be misidentified
# - it's meant for music so it will probably not work well for SFX/voices
# - may work better when ordering untagged files (use .txtp + renames)
#
# Install dependencies:
# - vgmstream-cli in PATH if some files aren't wav/ogg/flac.
# - pip install librosa, numpy
# - pip install tinytag
#   - optional, to read tags (defaults to filename parsing if not found)

#TODO: improve artist/album autotagging
#TODO: improve file tags


import os, re, argparse, enum, logging, subprocess, glob, shutil, time, collections
import librosa, numpy, json
import warnings

try:
    import tinytag
except:
    pass #optional

log = logging.getLogger(__name__)

RENAME_UTF8=True
COPY_UTF8=True
AUTO_THRESHOLD=-1
BASE_THRESHOLD=100.0
WRONG_THRESHOLD=0.0
TEMPO_DEVIATION_MAX=10.0
DEFAULT_THRESHOLD=AUTO_THRESHOLD
DEFAULT_RESAMPLE=22050
DEFAULT_LENGTH=15.0
DEFAULT_TAGGED='tagged'
DEFAULT_UNTAGGED='untagged'

class ComparisonMethod(enum.Enum):
    COSINE = 'cos'
    DTW = 'dtw'
    EUCLIDEAN = 'euc'
    AUTO = 'auto'

class OrderMethod(enum.Enum):
    TAGS = 'tags'
    FILES = 'files'

#----------------------------------------------------------------------------------------------------------------------
# cly.py

class Cli(object):
    def _parse(self):
        description = (
            "Compares files from one tagged folder vs other untagged folder and makes a !tags.m3u based on tagged filenames\n"
        )
        epilog = (
            "examples:\n"
            "  %(prog)s -s 30.0 -r 11050\n"
        )

        p = argparse.ArgumentParser(description=description, epilog=epilog, formatter_class=argparse.RawTextHelpFormatter)
        p.add_argument('-dt',   '--dir-tagged',     help="Folder with tagged files", default=DEFAULT_TAGGED)
        p.add_argument('-du',   '--dir-untagged',   help="Folder with untagged files", default=DEFAULT_UNTAGGED)
        p.add_argument('-fu',   '--files-untagged', help="Files (like **/*.txtp) in untagged folder (default: auto)", nargs='*')
        p.add_argument('-ft',   '--files-tagged',   help="Files (like **/*.flac) in tagged folder (default: auto)", nargs='*')
        p.add_argument('-t',    '--threshold',      help="Min percent of similarity to accept, up to 100 (default: auto)", type=float, default=DEFAULT_THRESHOLD)
        p.add_argument('-dv',   '--duration-variation', help="Max deviation of time between files (default: ignored)", type=float, default=-1)
        p.add_argument('-dl',   '--duration-loops', help="Number of loops used in duration calculation", type=float, default=2)
        p.add_argument('-df',   '--duration-fade',  help="Fade time used in duration calculation", type=float, default=10.0)
        p.add_argument('-tv',   '--tempo-variation',help="Max deviation of tempo (default: auto)", type=float, default=TEMPO_DEVIATION_MAX)
        p.add_argument('-mo',   '--match-once',     help="Match a tagged file only once\n(matching multiple times is useful for song variations)", action='store_true')
        p.add_argument('-r',    '--resample',       help="Resample value (smaller = faster but less accurate)", type=int, default=DEFAULT_RESAMPLE)
        p.add_argument('-s',    '--seconds',        help="Seconds to compare (smaller = faster but less accurate)", type=float, default=DEFAULT_LENGTH)
        p.add_argument('-v',    '--log-level',      help="Verbose log level (off|debug|info, default: info)", default='info')
        p.add_argument('-q',    '--quicker',        help="Simplifies some calculations to speed up matching", action='store_true')
        p.add_argument('-m',    '--method',         help="Comparator method (multiple|dtw|euc|cos, default: multiple)", default=ComparisonMethod.AUTO)
        p.add_argument('-to',   '--tags-order',     help="Set how tags.m3u files are sorted (files|tags, default: auto)", default=OrderMethod.TAGS)
        p.add_argument('-taa',  '--tags-add-artist',help="Include 'artist' (if found)", action='store_true')
        p.add_argument('-tat',  '--tags-add-track', help="Include 'track' and 'discs' per file (if found)", action='store_true')
        p.add_argument('-tis',  '--tags-info-score',help="Include similarity scores in tags (for easier identifying wrong stuff)", action='store_true')
        p.add_argument('-tif',  '--tags-info-file', help="Include 'tagged' filename (for rips where title<>filename differs)", action='store_true')
        args = p.parse_args()

        return args
    
    def start(self):
        args = self._parse()
        return args

#----------------------------------------------------------------------------------------------------------------------
# utils.py

class Logger(object):
    def __init__(self, args):
        levels = {
            'info': logging.INFO,
            'debug': logging.DEBUG,
        }
        self.level = levels.get(args.log_level, logging.ERROR)

    def setup(self):
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        
        log.setLevel(self.level)

        # some librosa warning in certain files
        warnings.filterwarnings("ignore", category=UserWarning)


class FileLoader():
    IGNORED_EXTS = ('.bat', '.sh', '.exe', '.dll', '.m3u', '.7z', '.zip', '.rar', '.txt', '.lnk', '.py', '.cue', '.png', '.jpg', '.jpeg', '.db')

    @staticmethod
    def find_files(root_dir, filters=None):
        if not root_dir:
            root_dir = '.'
        if not filters:
            filters = ['**/*.*']

        files = []
        for filter in filters:
            filter = root_dir + '/' + filter
            files += glob.glob(filter, recursive=True)

        files = [f for f in files if not f.lower().endswith(FileLoader.IGNORED_EXTS)]
        files = [f for f in files if os.path.isfile(f)]
        files = list(set(files))
        return files

class Timer:
    def __init__(self):
        self.start()

    def start(self):
        self._time = time.time()

    def stop(self):
        end_time = time.time()
        elapsed = end_time - self._time
        return elapsed


#----------------------------------------------------------------------------------------------------------------------
# tags.py

class TagInfo:
    def __init__(self, filepath):
        self.title = None
        self.artist = None
        self.album = None
        self.track = None
        self.disc = None
        self.duration = None
        self.filename = None
        self._read_tags(filepath)

    def _read_tags(self, filepath):
        self.filename = os.path.basename(filepath)
        self.dirname = os.path.dirname(filepath)

        filename = self.filename

        try:
            tag = tinytag.TinyTag.get(filepath)
            if tag.title:
                self.title = tag.title
                self.artist = tag.artist
                self.album = tag.album
                self.track = tag.track
                self.disc = tag.disc
                self.duration = tag.duration
                return
        except Exception:
            log.debug("error using TinyTag (not installed?), reding file tags")
            pass

        # Fallback to filename parsing
        name, _ = os.path.splitext(filename)
        parts = name.split(' - ')

        # replace " - " and single spaces after track number
        name = re.sub(r'^(\d+)[\s-]+', r'\1 - ', name)
        parts = name.split(' - ')

        if len(parts) >= 4:
            # Format: track - artist - title - more title
            self.track = self._parse_track(parts[0])
            self.artist = parts[1].strip()
            self.title = ' - '.join(parts[2:]).strip()

        elif len(parts) == 3:
            # Format: track - artist - title
            self.track = self._parse_track(parts[0])
            self.artist = parts[1].strip()
            self.title = parts[2].strip()

        elif len(parts) == 2:
            if self._is_track_number(parts[0]):
                # Format: track - title
                self.track = self._parse_track(parts[0])
                self.title = parts[1].strip()
            else:
                # Format: artist - title
                self.artist = parts[0].strip()
                self.title = parts[1].strip()

        elif len(parts) == 1:
            # Format: title only
            self.title = parts[0].strip()

        return self

    @staticmethod
    def _parse_track(track_str):
        try:
            return int(re.match(r'\d+', track_str).group())
        except Exception:
            return None

    @staticmethod
    def _is_track_number(s):
        return bool(re.match(r'^\d+$', s.strip()))

    def __repr__(self):
        attrs = vars(self)
        return f"TagInfo({', '.join(f'{k}={repr(v)}' for k, v in attrs.items())})"


class TagsLoader:

    def load_tags(self, results):
        log.info(f"loading tags...")
        timer = Timer()

        parsed_tags = {} # don't reload when multiple untagged match with the same tagged

        for result in results:
            if not result.file_tg:
                continue

            if result.file_tg in parsed_tags:
                tags = parsed_tags[result.file_tg]
            else:
                tags = TagInfo(result.file_tg)
                parsed_tags[result.file_tg] = tags
            result.tags = tags

        elapsed = timer.stop()
        log.info(f"done (elapsed {elapsed:.2f}s)")


#----------------------------------------------------------------------------------------------------------------------
# tagsm3u.py

class TagsM3uMaker:
    def __init__(self, args, ):
        self._args = args
        self._lines = None

    @staticmethod
    def _count_artists(results):
        artist_counts = {}

        for result in results:
            tags = result.tags
            if tags and tags.artist:
                if tags.artist in artist_counts:
                    artist_counts[tags.artist] += 1
                else:
                    artist_counts[tags.artist] = 1

        return artist_counts

    @staticmethod
    def _get_album_name(results):
        for result in results:
            tags = result.tags
            if not tags:
                continue
            if tags.album:
                return tags.album

            # use first dir after 'tagged': 'tagged/Blah/disc1' > 'Blah'
            dirname = tags.dirname if tags.dirname else ''
            pos = dirname.find(os.sep)
            if pos >= 0:
                dirname = dirname[pos+1:]
            pos = dirname.find(os.sep)
            if pos >= 0:
                dirname = dirname[:pos]
            pos = dirname.find('(')
            if pos >= 0:
                dirname = dirname[:pos]
            return dirname
        return ''

    def _add_tags(self, result, untagged_flag=False):
        tags = result.tags
        file_ut = result.file_ut
        score = result.score

        if self._args.tags_info_score and score:
            self._lines.append(f'## score: {score:.3f}')
        if self._args.tags_info_file and result.basename_tg:
            self._lines.append(f'## file: {result.basename_tg}')

        if tags:
            extra = ''
            if not file_ut:
                extra = '#'

            if tags.disc is not None and self._args.tags_add_track:
                self._lines.append(f'{extra}# %DISC     {tags.disc}')

            if tags.track is not None and self._args.tags_add_track:
                self._lines.append(f'{extra}# %TRACK    {tags.track}')

            if tags.artist and self._args.tags_add_artist:
                self._lines.append(f'{extra}# %ARTIST   {tags.artist}')

            if tags.title:
                self._lines.append(f'{extra}# %TITLE    {tags.title}')
        
        if not untagged_flag:
            final_path = os.path.basename(file_ut) if file_ut else '#?'
            self._lines.append(f'{final_path}')


    def _make_tagsm3u(self, results, folder):
        self._lines = []

        printed_missing_ut = False
        printed_missing_tg = False

        is_order_tags = OrderMethod.TAGS == OrderMethod(self._args.tags_order)
        prev_track = 0

        # main tags
        for result in results:
            #if len(result.tags_list) > 1:
            #    log.info(f"multiple tags for {result.file_ut} (tweak detection parameters)")
            #    self._lines.append(f'## multitags')

            # separation between 'discs'
            if is_order_tags and result.tags and result.tags.track:
                if prev_track and result.tags.track < prev_track:
                    self._lines.extend(['', ''])
                prev_track = result.tags.track

            # print header first time missing_ut appears (should be sorted at the bottom)
            is_missing_ut = result.file_tg is None
            if not printed_missing_ut and is_missing_ut:
                self._lines.extend(['', ''])
                self._lines.append('## missing untagged files')
                printed_missing_ut = True

            # print header first time missing_tg appears (should be sorted at the bottom, but only in some cases)
            is_missing_tg = result.file_ut is None and not is_order_tags
            if not printed_missing_tg and is_missing_tg:
                self._lines.extend(['', ''])
                self._lines.append('## missing tagged files')
                printed_missing_tg = True

            self._add_tags(result)

        self._lines.append('')


        # header tags
        album = self._get_album_name(results)
        header = []
        header.append(f'# @ALBUM    {album}')
        #if join_artists:
        #    header.append('# @ARTIST   %s' % (', '.join(artists)))
        if not self._args.tags_add_artist and len(self._artist_counts) == 1:
            artist = next(iter(self._artist_counts))
            header.append(f'# @ARTIST   {artist}')

        header.append('# $AUTOTRACK')
        header.append('#')
        header.append('')
        header.append('')

        tags_path = folder + '/!tags.m3u'
        with open(tags_path, 'w', encoding='utf-8-sig') as f:
            f.write('\n'.join(header))
            f.write('\n'.join(self._lines))


    @staticmethod
    def _split_results(results, default_dir):
        folder_map = collections.OrderedDict()

        # results without matches can be mixed in depending on sorting options, put them
        # in last used dir (with other matched results)
        last_dir = next(
            (os.path.dirname(result.file_ut) for result in results if result.file_ut), default_dir
        )

        for result in results:
            if result.file_ut:
                folder = os.path.dirname(result.file_ut)
                last_dir = folder
            else:
                folder = last_dir

            if folder not in folder_map:
                folder_map[folder] = []
            folder_map[folder].append(result)

        return folder_map


    def process(self, results):
        log.info(f"generating !tags.m3u...")

        self._artist_counts = self._count_artists(results)

        Sorter(self._args).sort_results(results)

        # tagsm3u must reside in folder's files, so group by folder
        # (meaning it will create one .m3u per untagged subfolder with files)
        folder_map = self._split_results(results, self._args.dir_untagged)

        for folder in folder_map.keys():
            results = folder_map.get(folder)

            self._make_tagsm3u(results, folder)

        log.info("done")


#----------------------------------------------------------------------------------------------------------------------
# analysis.py

class Converter:
    # supported formats that Librosa can read directly (.mp3 in some cases but no matter)
    LIBROSA_EXTS = ('.wav', '.lwav', '.flac', '.ogg')

    def __init__(self, args):
        self._output_path = None
        self._copy_path = None
        self._args = args
        self._vgmstream_path = 'vgmstream-cli'

    @staticmethod
    def _is_utf8(s):
        return not s.isascii()

    @staticmethod
    def _sanitize_utf8_filename(s):
        if s.isascii():
            return s
        s = ''.join(c if ord(c) < 128 else '_' for c in s)
        name, ext = os.path.splitext(s)
        return f"{name}.temp{ext}"

    # approximate calculation (mainly for streams vs gamerips since they often stick to defaults)
    def _decode_duration(self, result):
        try:
            loop_count = self._args.duration_loops
            fade_time = self._args.duration_fade

            json_result = result.stdout

            # extra crap when debug output is set, ignore
            pos1 = json_result.find(b'{"')
            if pos1 > 0:
                json_result = json_result[pos1:]
            pos2 = json_result.rfind(b'}')
            if pos2 < len(json_result) :
                json_result = json_result[:pos2+1]

            jout = json.loads(json_result.decode('utf-8'))

            sample_rate = jout['sampleRate']
            samples = jout['numberOfSamples']
            if loop_count and 'loopingInfo' in jout and jout['loopingInfo']:
                loop_info = jout['loopingInfo']
                loop_start = loop_info['start']
                loop_end = loop_info['end']

                fade_samples = fade_time * sample_rate
                play_samples = loop_start + (loop_end - loop_start) * loop_count + fade_samples
            else:
                play_samples = samples

            return play_samples / sample_rate
        except Exception as e:
            log.info("couldn't parse duration from vgmstream output", e)
            return None

    def convert(self, input_path):
        duration = -1
        duration_variation = self._args.duration_variation
        original_path = input_path

        # no conversion needed, but still load duration
        # this can be gotten with tinytag but not sure about accuracy
        is_librosa_file = False
        ext = os.path.splitext(input_path)[1].lower()
        if ext in Converter.LIBROSA_EXTS:
            is_librosa_file = True
            self._output_path = None
            # no need to calculate duration
            if duration_variation < 0.0:
                return input_path, duration

        # vgmstream can't handle UTF-8 paths, so make a non-utf8 clone + delete after
        # (slower and could also rename + unrename but feels be riskier)
        self._copy_path = None
        if self._is_utf8(input_path):
            self._copy_path = self._sanitize_utf8_filename(input_path)
            shutil.copy(input_path, self._copy_path)
            input_path = self._copy_path

        self._output_path = input_path

        max_length = 100
        if len(self._output_path) > max_length:
            self._output_path = self._output_path[:max_length]
        self._output_path += ".temp.wav"

        # limit decode seconds to speed up conversion
        if self._args.seconds and self._args.seconds > 0.0:
            input_path = f"{input_path} #b {args.seconds}.txtp"

        #log.debug(f"decoding {input_path}")
        try:
            command = [self._vgmstream_path, '-I', '-i', '-o', self._output_path, input_path]
            if is_librosa_file and duration_variation >= 0.0:
                command.append("-m") #metadata only
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if duration_variation >= 0.0:
                duration = self._decode_duration(result)
            if self._copy_path:
                os.remove(self._copy_path)
        except FileNotFoundError:
            if self._copy_path:
                os.remove(self._copy_path)
            raise RuntimeError("vgmstream-cli not installed or not in PATH")
        except subprocess.CalledProcessError as e:
            #raise RuntimeError(f"vgmstream conversion failed: {e.stderr.decode().strip()}")
            # presumably not an audio file
            if self._copy_path:
                os.remove(self._copy_path)
            return None, duration

        if is_librosa_file:
            return original_path, duration

        return self._output_path, duration

    def cleanup(self):
        if not self._output_path or not self._output_path.endswith('.temp.wav') or not os.path.isfile(self._output_path):
            return
        os.remove(self._output_path)
        self._output_path = None


# Some info: https://github.com/markstent/audio-similarity#metrics
class FeatureSet():
    def __init__(self, args, y, sr, duration):
        self._args = args
        self.duration = duration
        self._parse_features(y, sr)

    # extract feature sequences (array of numbers)
    # some of these are slow and not that useful, to be researched
    def _parse_features(self, y, sr):
        quick_mode = self._args.quicker

        # calculate librosa features, usually arrays of rows (headers) x columns (time)
        # to analyze we use feature.T = transposed (columns), or use axis=1 (also columns)

        self.features = []
        ft = self.features

        # timbral texture (13 coefs), low distinctiveness but maybe useful for vocals?
        #mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)

        # harmonic/pitch features (12 notes), for music all seem pretty distinctive (stft a bit less)
        # since it's only about pitch it should be combined with others
        if quick_mode:
            ft += [librosa.feature.chroma_stft(y=y, sr=sr)]   #distinctive enough
        else:
            ft += [librosa.feature.chroma_cqt(y=y, sr=sr)]     #distinctive
            ft += [librosa.feature.chroma_cens(y=y, sr=sr)]   #distinctive
            #chroma_vqt = librosa.feature.chroma_vqt(y=y, sr=sr, intervals='equal', bins_per_octave=12)

        # rhythm features
        # without envelope it gets wrong same tracks from different sources (ex. mp3 vs hca), not sure about performance
        onset_envelope = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, _beat_times = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_envelope)
        tempo = tempo[0] if isinstance(tempo, numpy.ndarray) else tempo

        # doesn't seem to work well with different sources
        #y_norm = librosa.util.normalize(y)
        #stft = librosa.stft(y_norm)
        #stft_db = librosa.amplitude_to_db(abs(stft))
        #ft += [stft_db]

        #TO-DO: the following may not work resampled, not sure how to properly handle fmin
        #fmin = 200.0 #default
        #if sr < 22050:
        #    fmin = fmin * (sr / 22050)

        #fourier_tempogram = librosa.feature.fourier_tempogram(y=y, sr=sr)
        # various timbre related stuff, not distinctive enough (very close scores between different songs)
        # spread of frequencies (not distinctive)
        #spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
        # diffs between peaks and valleys (so-so)
        #spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
        # brightness
        #spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        # energy frequencies?
        #spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
        # noisiness or percussiveness
        #zcr = librosa.feature.zero_crossing_rate(y)

        # rhythmic stuff
        #tempogram = librosa.feature.tempogram(y=y) #somewhat distinctive
        # harmonic relationships (not useful)
        #tonnetz = librosa.feature.tonnetz(y=librosa.effects.harmonic(y), sr=sr)
        # passable 
        #onset_strength = librosa.onset.onset_strength(y=y, sr=sr)

        # structure (not useful or not sure how to use)
        #recurrence_matrix  = librosa.segment.recurrence_matrix(?)
        #agglomerative = librosa.segment.agglomerative(?)

        rms = librosa.feature.rms(y=y)
        self.loudness = numpy.mean(rms)

        self.tempo = tempo

        #self.features = [
            #mfcc,
            #chroma_stft,
            #chroma_cqt,
            #chroma_cens,
            #chroma_vqt,
            #fourier_tempogram,
            #spectral_bandwidth,
            #spectral_contrast,
            #spectral_centroid,
            #spectral_rolloff,
            #zcr,
            #tempogram,
            #tonnetz,
            #onset_strength,
        #]

        # normalize: seems to decrease accuracy
        if False:
            self.features = [librosa.util.normalize(x, axis=1) for x in self.features]
        if False:
            features = []
            for feature in self.features:
                feature_min = feature.min(axis=1, keepdims=True)
                feature_max = feature.max(axis=1, keepdims=True)
                feature_scaled = (feature - feature_min) / (feature_max - feature_min)
                features.append(feature_scaled)
            self.features = features

        # cache
        self.features_mean = []
        for feature in self.features:
            axis = 1 if feature.ndim > 1 else 0
            self.features_mean.append(numpy.mean(feature, axis=axis))


class Comparator():
    def __init__(self, args):
        self._args = args
        self._features = {}

    # extract feature sequences (array of numbers)
    def _extract_features(self, path):
        resample = self._args.resample
        if resample <= 0.0:
            resample = None #default 22050

        seconds = self._args.seconds
        if seconds <= 0.0:
            seconds = None

        converter = Converter(self._args)

        out_path, duration = converter.convert(path) #creates temp file for librosa if needed
        if not out_path:
            log.info(f"can't parse: {path}")
            return None

        try:
            # librosa downmixes to mono and resamples for better results
            y, sr = librosa.load(out_path, sr=resample, duration=seconds)
        except:
            raise ValueError(f"Failed to analyze {path}") # from e

        converter.cleanup() # deletes temp file if needed

        features = FeatureSet(self._args, y, sr, duration)
        return features

    @staticmethod
    def _cosine_similarity(vec1, vec2):
        dot_product = numpy.dot(vec1, vec2)
        norm1 = numpy.linalg.norm(vec1)
        norm2 = numpy.linalg.norm(vec2)
        epsilon = 1e-8
        dist = (dot_product / (norm1 * norm2 + epsilon))
        #dist = dot_product / (norm1 * norm2) if norm1 and norm2 else 0.0
        return dist

    @staticmethod
    def _euclidean_similarity(vec1, vec2):
        dist = numpy.linalg.norm(vec1 - vec2)
        return 1 / (1 + dist)

    @staticmethod
    def _dtw_similarity(f1, f2):
        D, wp = librosa.sequence.dtw(X=f1, Y=f2, backtrack=True) #, metric='euclidean'
        score = D[-1, -1] / len(wp)
        return 1 / (1 + score)

    @staticmethod
    def _tempo_deviation(t1, t2):
        deviation = abs(t1 - t2)
        similarity = 1.0 / (1.0 + deviation / max(t1, t2, 1e-8))
        return (similarity, deviation)

    @staticmethod
    def _duration_deviation(t1, t2):
        deviation = abs(t1 - t2)
        #similarity = 1.0 / (1.0 + deviation / max(t1, t2, 1e-8))
        return deviation

    @staticmethod
    def _loudness_similarity(rms1, rms2):
        max_rms = max(rms1, rms2)
        if max_rms == 0:
            return 1.0 if rms1 == rms2 else 0.0

        diff = abs(rms1 - rms2) / max_rms
        similarity = 1.0 - diff
        return similarity

    def _add_comparison(self, similarity, weight, info=True):
        #if similarity == 1.0 and info:
        #    log.info("exact match found") #rare but possible

        self._temp_scores.append(similarity)
        self._temp_weights.append(weight)

    # Calculates the distance between two feature arrays.
    # Higher distances mean less likely the files are the similar.
    # Mostly done by blindly testing random stuff until something worked (iow-- may be improved)
    def _compare_features(self, f1, f2):
        method = ComparisonMethod(self._args.method)

        self._temp_scores = []
        self._temp_weights = []

        # useful to reject very different cases ASAP
        tempo_sim = tempo_dev = None
        if True: #method == ComparisonMethod.MULTIPLE:
            tempo_sim, tempo_dev = self._tempo_deviation(f1.tempo, f2.tempo)
            if tempo_dev > self._args.tempo_variation:
                log.debug(f"ignored by tempo deviation={tempo_dev}")
                return 0.0
            self._add_comparison(tempo_sim, 0.25, info=False)

        if self._args.duration_variation >= 0.0 and f1.duration and f2.duration:
            duration_dev = self._duration_deviation(f1.duration, f2.duration)
            if duration_dev > self._args.duration_variation:
                log.debug(f"ignored by duration deviation={duration_dev}")
                return 0.0

        if True: #method == ComparisonMethod.MULTIPLE:
            # possibly not useful vs OSTs but may help with normal<>quiet variations seems useful overall
            loudness_sim = self._loudness_similarity(f1.loudness, f2.loudness)
            self._add_comparison(loudness_sim, 0.25, info=False)


        #xsim = librosa.segment.cross_similarity(f1_feature, f2_feature, metric='euclidean', mode='affinity')

        # usually good but a bit slow
        if  method == ComparisonMethod.DTW or method == ComparisonMethod.AUTO:
            weight = 2.5
            for f1_feature, f2_feature in zip(f1.features, f2.features):
                sim = self._dtw_similarity(f1_feature, f2_feature)
                self._add_comparison(sim, weight)

        # good enough and fast
        if method == ComparisonMethod.EUCLIDEAN or method == ComparisonMethod.AUTO:
            weight = 1.0
            for f1_feature, f2_feature in zip(f1.features_mean, f2.features_mean):
                sim = self._euclidean_similarity(f1_feature, f2_feature)
                self._add_comparison(sim, weight)

        # gives similarities clumped together (0.999 for match, 0.95 for incorrect) so not too useful
        if method == ComparisonMethod.COSINE:
            weight = 0.25
            for f1_feature, f2_feature in zip(f1.features_mean, f2.features_mean):
                sim = self._cosine_similarity(f1_feature, f2_feature)
                self._add_comparison(sim, weight)

        total_weight = sum(self._temp_weights)
        final_score = sum(f * w for f, w in zip(self._temp_scores, self._temp_weights)) / total_weight
        
        log.debug(f"  final score: {final_score:.3f} (tempo dev={tempo_dev}, scores={self._temp_scores})")
        return final_score * 100.0


    def add(self, path):
        log.debug(f"file: {path}")
        
        if path in self._features:
            return
        file_features = self._extract_features(path)
        if file_features is None:
            return
        self._features[path] = file_features

    def add_files(self, paths):
        for path in paths:
            self.add(path)

    def compare(self, path1, path2):
        feat1 = self.get(path1)
        feat2 = self.get(path2)
        if feat1 is None or feat2 is None:
            return WRONG_THRESHOLD

        log.debug(f"comparing\n- {path1}\n- {path2}")
        return self._compare_features(feat1, feat2)

    def get(self, path):
        
        return self._features.get(path)


#----------------------------------------------------------------------------------------------------------------------
# results.py

class Sorter:
    def __init__(self, args):
        self._args = args

    @staticmethod
    def get_natsort_str(s):
        # ugly but otherwise sorts filenames like: '1', '11', '100', '2'
        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

    @staticmethod
    def _sort_by_tags(result):

        sort_items = []

        score = -result.score #higher score first

        tags = result.tags
        dirname = tags.dirname if tags and tags.dirname else ''
        filename = tags.filename if tags and tags.filename else ''
        disc = tags.disc if tags and tags.disc is not None else float('inf')
        track = tags.track if tags and tags.track is not None else float('inf')
        title = tags.title if tags and tags.title else ''
        is_matched = tags is None # files not matched go at the bottom

        dirname = Sorter.get_natsort_str(dirname)
        filename = Sorter.get_natsort_str(filename)

        sort_items.append(is_matched)
        # dir first for better order when mixing tags from multiple albums
        sort_items.append(dirname) 
        sort_items.append(disc)
        sort_items.append(track)
        if tags and tags.track:
            sort_items.append('') #in case filename is wonky
        else:
            sort_items.append(filename)
        sort_items.append(title)
        sort_items.append(score)

        if not tags and result.file_ut:
            # for missing untagged
            file_ut = result.file_ut if result.file_ut else ''

            file_ut = Sorter.get_natsort_str(file_ut)
            sort_items.append(file_ut)
        else:
            sort_items.append('')

        return sort_items

    @staticmethod
    def _sort_by_file_ut(result):
        is_matched = result.file_ut is None
        file_ut = result.file_ut if result.file_ut else ''

        file_ut = Sorter.get_natsort_str(file_ut)

        return (is_matched, file_ut)


    def sort_results(self, results):
        order = OrderMethod(self._args.tags_order)
        if order == OrderMethod.TAGS:
            results.sort(key=lambda result: self._sort_by_tags(result))
        else:
            results.sort(key=lambda result: self._sort_by_file_ut(result))

    def sort_files(self, files):
        files.sort(key=lambda file: Sorter.get_natsort_str(file))

    def sort_matches(self, matches):
        matches.sort(key=lambda result: -result.score)


class FileMatch:
    def __init__(self, file_ut=None, file_tg=None, score=0.0):
        self.file_ut = file_ut
        self.file_tg = file_tg
        self.tags = None
        self.score = score
        self.basename_ut = os.path.basename(file_ut) if file_ut else None
        self.basename_tg = os.path.basename(file_tg) if file_tg else None


#----------------------------------------------------------------------------------------------------------------------
# process.py

class App():

    def __init__(self, args):
        self.comparator = Comparator(args)
        self._args = args

    def _analyze(self, comparator, folder, file_filter, name):
        loader = FileLoader()

        files = loader.find_files(folder, file_filter)
        Sorter(self._args).sort_files(files)

        log.info(f"analyzing {len(files)} '{name}' files...")
        timer = Timer()

        comparator.add_files(files)

        elapsed = timer.stop()
        log.info(f"done (elapsed {elapsed:.2f}s)")
        return files

    @staticmethod
    def _calculate_threshold(ut_matches, max_score):
        scores = []
        for matches in ut_matches.values():
            match = max(matches, key=lambda match: match.score) # not sorted yet so use max
            scores.append(match.score)

        scores = numpy.array(scores)

        mean = numpy.mean(scores)
        std = numpy.std(scores)
        value = (mean + 0.5 * std) * 0.65

        #value = numpy.percentile(scores, 50.0)

        return value

    def _find_matches(self, ut_files, tg_files, comparator):
        log.info(f"finding matches...")
        timer = Timer()

        threshold = self._args.threshold
        auto_threshold = threshold == AUTO_THRESHOLD
        max_score = 0.0

        # for flexibility save all matches then later cull by top scores/autothreshold
        ut_matches = collections.OrderedDict()
        for file_ut in ut_files:

            for file_tg in tg_files:
                try:
                    score = comparator.compare(file_ut, file_tg)
                except Exception as e:
                    raise RuntimeError(f"Error comparing {file_ut} vs {file_tg}") from e

                if score > max_score:
                    max_score = score
                if score <= 0:
                    continue
                if not auto_threshold and score < threshold:
                    continue

                # update scores
                match = FileMatch(file_ut, file_tg, score)

                if file_ut not in ut_matches:
                    ut_matches[file_ut] = []
                ut_matches[file_ut].append(match)

                log.debug(f"Possible pair (score: {match.score:.3f})\n- {match.basename_ut}\n- {match.basename_tg}")

        elapsed = timer.stop()


        # approximate % depending on average scores (more or less)
        if auto_threshold:
            threshold = self._calculate_threshold(ut_matches, max_score)


        # get best match for each file_ut
        tg_used = set()
        results = []
        sorter = Sorter(self._args)
        for matches in ut_matches.values():
            matches = [match for match in matches if match.score >= threshold]
            sorter.sort_matches(matches)
            #ut_matches[ut] = matches
            
            if self._args.match_once:
                match = next((match for match in matches if match.file_tg not in tg_used), None)
            else:
                match = next(iter(matches), None)
            if not match:
                continue

            tg_used.add(match.file_tg)
            results.append(match)

        log.info(f"done: max score={max_score:.3f}, threshold={threshold:.3f} (elapsed {elapsed:.2f}s)")
        return results

    @staticmethod
    def _add_missing(results, ut_files, tg_files):
        missing_ut = set(ut_files) - set(result.file_ut for result in results)
        missing_tg = set(tg_files) - set(result.file_tg for result in results)

        # merge with current; will be identified and sorted in later parts

        for file_ut in missing_ut:
            result = FileMatch(file_ut=file_ut)
            results.append(result)

        for file_tg in missing_tg:
            result = FileMatch(file_tg=file_tg)
            results.append(result)


    def start(self):
        comparator = Comparator(args)

        ut_files = self._analyze(comparator, self._args.dir_untagged, self._args.files_untagged, 'untagged')
        if not ut_files:
            log.info(f"no untagged files found")
            return

        tg_files = self._analyze(comparator, self._args.dir_tagged, self._args.files_tagged, 'tagged')
        if not tg_files:
            log.info(f"no tagged files found")
            return

        results = self._find_matches(ut_files, tg_files, comparator)
        if not results:
            log.info(f"no matched results found")
            return

        # include missing in the result list so they can be sorted and their tags read as one
        self._add_missing(results, ut_files, tg_files)

        TagsLoader().load_tags(results)

        TagsM3uMaker(self._args).process(results)


if __name__ == "__main__":
    args = Cli().start()
    Logger(args).setup()
    App(args).start()
