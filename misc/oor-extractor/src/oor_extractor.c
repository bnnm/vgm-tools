/* .oor dumper by bnnm
 *
 * Finds .oor files by reading bigfiles and looking for valid .oor headers.
 * Format is bitpacked and some parts may be ambiguous, but it should fail midway on bad data.
 * If possible also extracts metadata that sometimes goes before .oor, which may have loops.
 *
 * - compilation (gcc or any equivalent should work; note you need 64-bit for >2GB files)
 * gcc -m64 -Wall -O2  memmapping.c oor_reader.c oor_extractor.c -o oor-extractor.exe
*/

#define VERSION "2025.02.25"

#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "bitstream_msb.h"
#include "memmapping.h"

#define OOR_MIN_SIZE 0x200 // to ignore false positives, ~0x1000 seem to exist


typedef struct {
    bool test;
    bool verbose;
    bool skip_metadata;
    int min_size;
    const char* basename;
    int filenames[0x100];
    int filename_count;
} settings_t;


extern int read_oor(uint8_t* buf, uint32_t left);
extern bool check_oor(uint8_t* buf, uint32_t left);


// OOR is bitpacked but try to determine if bytes look like a .oor
// (will fail later if we picked a wrong candidate)
static bool is_candidate_oor(uint8_t* data, size_t file_size) {
    static uint8_t empty_granule[0x09];

    if (file_size < 0x50)
        return false;
    
    int page_version;
    int head_pos;
    if (data[0x00] == 0x48 && memcmp(data + 0x01, empty_granule, 9) == 0) {
        // V1: bits 01 0010 00 + granule + header
        head_pos = 0x0A;
        page_version = 1;
    }
    else if (data[0x00] == 0x08) {
        // V0: bits 00 0010 00 + header
        head_pos = 0x01;
        page_version = 0;
    }
    else {
        return false;
    }
    
    uint16_t head = (data[head_pos] << 8) | data[head_pos+1];
    int version     = (head >> 14) & 0x03; //2b
    int channels    = (head >> 11) & 0x07; //3b
    int sr_selector = (head >> 9) & 0x03; //3b
    int srate       = (head >> 1) & 0xFF; //3b

    if (version != page_version || channels == 0)
        return false;

    if (sr_selector == 3 && srate > 10)
        return false;

    return true;
}


// detect companion metadata, which seems to to together with .oor for bgm and may have loops.
// Format looks the same in all versions (PC/Vita/PS3) and can be find with v0 and v1 files, usually for files with codebook.
// From tests bgm is loaded with 2 pointers, one to this metadata and other to the .oor itself.
// Some files have multiple metadata closeby, but only closest one to header matters.
static int read_metadata(uint8_t* data, uint32_t oor_offset) {
    int rewind_bytes = 0x150;
    if (rewind_bytes > oor_offset)
        rewind_bytes = oor_offset;
    if (rewind_bytes < 0x10)
        return 0;
    uint32_t limit = oor_offset - rewind_bytes;
    uint32_t offset = oor_offset - 0x08;
    data -= 0x08; //odd but legal

    while (offset > limit) {
        // known format: 0x8003010* FFFF0100 ...
        // there are probably more variations (numbers are field counts?)
        if (data[0] == 0x80 && data[1] == 0x03 && data[2] == 0x01 &&
            data[4] == 0xFF && data[5] == 0xFF && data[6] == 0x01 && data[7] == 0x00) {
            int size = oor_offset - offset;
            return size;
        }
        data--;
        offset--;
    }

    return 0;
}

static void dump_file(uint8_t* data, int oor_size, const char* basename, uint32_t offset, int done, const char* ext) {
    char outname[0x1000] = {0};

    //snprintf(outname, sizeof(outname), "%s_%05i_0x%08x.oor", basename, done, offset);
    snprintf(outname, sizeof(outname), "%s_%05i.%s", basename, done, ext);

    //printf("dumped %s at %x\n", outname, offset);
    FILE* outfile = fopen(outname, "wb");
    if (!outfile) {
        printf("can't write %s\n", outname);
        return;
    }

    fwrite(data, oor_size, sizeof(uint8_t), outfile);
    fclose(outfile);
}

// read through the whole file to dump .oor
static int parse_file(settings_t* cfg, uint8_t* data, size_t file_size, const char* basename, int files) {
    int done = 0;
    uint32_t offset = 0;

    while (file_size) {
        int oor_size = 0; 

        if (is_candidate_oor(data, file_size)) {
            //printf("candidate oor at %x\n", offset);
            // will return 0 if not a valid .oor
            oor_size = read_oor(data, file_size);
        }
        
        if (oor_size < 0) {
            // ignore odd cases
            if (-oor_size > OOR_MIN_SIZE)
                printf("odd file at %x (%x)\n", offset, -oor_size);
        }
        
        if (oor_size > 0) {
            bool ok = check_oor(data, oor_size);
            if (!ok) {
                printf("odd file at %x (%x)\n", offset, oor_size);
            }

            bool extract = true;
            if (cfg->test || oor_size < cfg->min_size)
                extract = false;

            int curr_done = files + done;
            if (cfg->verbose) {
                printf(".oor %05i found at offset 0x%08x (size 0x%x)%s\n", curr_done, offset, oor_size, extract ? "" : " **skipped" );
            }
            if (extract) {
                dump_file(data, oor_size, basename, offset, curr_done, "oor");
            }

            if (!cfg->skip_metadata) {
                int metadata_size = read_metadata(data, offset);
                if (metadata_size > 0) {
                    if (cfg->verbose) {
                        printf(".oor %05i metadata found at offset 0x%08x (size 0x%x)%s\n", curr_done, offset - metadata_size, metadata_size, extract ? "" : " **skipped" );
                    }
                    if (extract) {
                        dump_file(data - metadata_size, metadata_size, basename, offset - metadata_size, curr_done, "bin");
                    }
                }
            }

            data += oor_size;
            file_size -= oor_size;
            offset += oor_size;

            done++;
        }
        else {
            data++;
            file_size--;
            offset++;
        }
    }

    return done;
}

static void load_basename(const char* filename, char* basename, int basename_len) {
    snprintf(basename, basename_len, "%s", filename);

    const char* dot = strrchr(filename, '.');
    if (!dot || dot == filename)
        return;

    size_t pos = dot - filename;
    basename[pos] = '\0';
}

static bool read_settings(settings_t* cfg, int argc, char* argv[]) {
    int i = 1;
    while (i < argc) {
        if (argv[i][0] == '-' && argv[i][1] != '\0') {
            char flag = argv[i][1];
            switch(argv[i][1]) {
                case 't':
                    cfg->test = true;
                    break;
                case 'v':
                    cfg->verbose = true;
                    break;
                case 'M':
                    cfg->skip_metadata = true;
                    break;
                case 's': {
                    i++;
                    if (i >= argc)
                        break;
                    const char* val = argv[i];
                    if (val[0]=='0' && val[1] == 'x')
                        cfg->min_size = (int)strtol(val, NULL, 16);
                    else
                        cfg->min_size = atoi(val);
                    break;
                }
                case 'b': {
                    i++;
                    if (i >= argc)
                        break;
                    const char* val = argv[i];
                    cfg->basename = val;
                    break;
                }
                default:
                    printf("unknown flag -%c\n", flag);
                    return false;
            }
        }
        else {
            if (cfg->filename_count >= sizeof(cfg->filenames))
                break;
            cfg->filenames[cfg->filename_count] = i;
            cfg->filename_count++;
        }

        i++;
    }

    if (cfg->filename_count == 0)
        return false;
    if (!cfg->basename)
        cfg->basename = argv[cfg->filenames[0]];

    return true;
}


int main(int argc, char* argv[]) {
    settings_t cfg = {0};

    if (!read_settings(&cfg, argc, argv)) {
        fprintf(stderr,
            ".oor extractor (%s) by bnnm\n"
            "\n"
            "Usage: %s [options] <input files>\n"
            "   -t: test only (no extraction done)\n"
            "   -v: verbose info\n"
            "   -M: don't extract .bin metadata (may have loop info)\n"
            "   -s <min-size>: skip files smaller than size\n"
            "   -b <basename>: base preffix for extracted files, auto otherwise\n"
            " * for split files include all of them as input, to be treated as 1\n"
            "   example: %s -s 0x10000 muvluv16.rio muvluv16.rio.002"
            , VERSION, argv[0], argv[0]);
        return 1;
    }


    // basename for output files
    char basename[0x1000] = {0};
    load_basename(cfg.basename, basename, sizeof(basename));

    int files = 0;
    for (int i = 0; i < cfg.filename_count; i++)  {
        int argv_index = cfg.filenames[i];
        const char* filename = argv[argv_index];

        printf("processing: %s\n", filename);

        // map file to simplify streaming
        map_t map = {0};
        if (!map_file(&map, filename)) {
            fprintf(stderr, "Failed to open/map input file\n");
            return 1;
        }

        // find all .oor
        int done = parse_file(&cfg, map.file_content, map.file_size, basename, files);
        files += done;

        // close stuff
        unmap_file(&map);
    }    

    printf("done: %i files\n", files);
    return 0;
}
