#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <ctype.h>

// FNV.EXE
// Reverses Wwise fnv hashes.
// 
// Some parts but have been coded for performance reasons, may be improved.
// We want to reduce ops+ifs, and calling separate functions with less ifs is a
// good way, though the copy-pasting could be improved with some inline'ing.
// fors are faster with fixed values, so it uses a list of allowed chars.


#define ENABLE_BANLIST  1

#define FNV_VERSION "1.0"

#define MAX_CHARS 64
#define MAX_TARGETS 512
#define MAX_BASE 1024 //in case of starting words
#define MAX_DEPTH 16
#define MAX_LETTERS 37
#define MAX_TABLE 123 //z= 123 = ASCII max

// constants
const char* dict = "ABCDEFGHIJKLMNOPQRSTUVWXYZ/._0123456789";
const char* list_name = "fnv.lst";
const char* list3_name = "fnv3.lst";
const int default_depth = 7;

// config
const int list_start = 0;
const int list_inner = 1;
uint8_t list3[2][MAX_TABLE][MAX_TABLE][MAX_TABLE];
char name[MAX_DEPTH + 1] = {0};
char base_name[MAX_BASE + 1] = {0};

static const uint8_t lookup_table[] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
    0x40, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
    0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x5B, 0x2F, 0x5D, 0x5E, 0x5F,
    0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
    0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
    0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F,
    0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F,
    0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
    0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
    0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
    0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
    0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF,
    0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF,
};


typedef struct {
    //config
    char start_letter;
    char end_letter;
    int begin_i;
    int end_i;

    char name_prefix[MAX_CHARS];
    char name_suffix[MAX_CHARS];
    int name_prefix_len;
    int name_suffix_len;

    int ignore_banlist;
    int print_text;
    int restrict_letters;
    int restrict_overwrite;

    //state
    const char* targets_s[MAX_TARGETS];
    uint32_t target;
    uint32_t targets[MAX_TARGETS];
    int targets_count;
    int reverse_names;

    int max_depth;
    int max_depth_1;

    int read_oklist;
    int list_threshold;

} fnv_config;

fnv_config cfg;


static void print_name(int depth) {
    printf("* match: ");

    if (cfg.name_prefix_len)
        printf("%s", cfg.name_prefix);

    if (depth >= 0)
        printf("%.*s", depth + 1, name);

    if (cfg.name_suffix_len)
        printf("%s", cfg.name_suffix);

    printf("\n");
}



// FNV is invertible, so fnv("abc") == ifnv("cba")
// this allows various optimizations (specially when mixing suffixes)
// thanks to jbosboom for pointing this out
//uint32_t ifnv(uint32_t h, string_view s) {
//    for (char c : s)
//        h = (h ^ c) * 0x359c449b;
//    return h;
//}

// with a suffix of length N, take expected final hash and undo last N steps
uint32_t ifnv_target(uint32_t hash, char* str, int len) {
    for (int n = len - 1; n >= 0; n--) {
        hash = (hash ^ str[n]) * 899433627; //inverse of prime 16777619
    }
    return hash;
}


// depth of exactly N letters
static void fvn_depth_max(const uint32_t cur_hash, const int depth) {

    // target will be in this loop (no need to check list)
    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];

        uint32_t new_hash = cur_hash;
        new_hash += lookup_table[elem];
        new_hash += (new_hash << 10);
        new_hash ^= (new_hash >> 6);

        uint32_t tmp_hash = new_hash;
        tmp_hash += (tmp_hash << 3);
        tmp_hash ^= (tmp_hash >> 11);
        tmp_hash += (tmp_hash << 15);
        
        if (tmp_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth);
        }
    }
}

// depth of N letters up to last
static void fvn_depth3(const uint32_t cur_hash, const int depth) {
    int pos = list_inner;
    char prev2 = name[depth-2];
    char prev1 = name[depth-1];
    

    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];
#if ENABLE_BANLIST
        if (!list3[pos][prev2][prev1][elem])
            continue;
#endif

        uint32_t new_hash = cur_hash;
        new_hash += lookup_table[elem];
        new_hash += (new_hash << 10);
        new_hash ^= (new_hash >> 6);

        uint32_t tmp_hash = new_hash;
        tmp_hash += (tmp_hash << 3);
        tmp_hash ^= (tmp_hash >> 11);
        tmp_hash += (tmp_hash << 15);
        
        if (tmp_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth);
        } 

        if (depth < cfg.max_depth_1) {
            name[depth] = elem;
            fvn_depth3(new_hash, depth + 1);
        }
        else {
            name[depth] = elem;
            fvn_depth_max(new_hash, depth + 1);
        }
    }
}

// depth of 3 letters (from start)
static void fvn_depth2(uint32_t cur_hash, int depth) {
    int pos = list_start;
    char prev2 = name[depth-2];
    char prev1 = name[depth-1];

    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];
#if ENABLE_BANLIST
        if (!list3[pos][prev2][prev1][elem])
            continue;
#endif

        uint32_t new_hash = cur_hash;
        new_hash += lookup_table[elem];
        new_hash += (new_hash << 10);
        new_hash ^= (new_hash >> 6);
#if 0
        uint32_t new_hash = (cur_hash * 16777619) ^ elem;
        if (new_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth);
        }
#endif
        if (depth < cfg.max_depth) {
            name[depth] = elem;
            fvn_depth3(new_hash, depth + 1);
        }
    }
}

// depth of 2 letters (from start)
static void fvn_depth1(uint32_t cur_hash, int depth) {

    for (int i = 0; i < MAX_LETTERS; i++) {
        char elem = dict[i];

        uint32_t new_hash = cur_hash;
        new_hash += lookup_table[elem];
        new_hash += (new_hash << 10);
        new_hash ^= (new_hash >> 6);
#if 0
        if (new_hash == cfg.target) {
            name[depth] = elem;
            print_name(depth);
        }
#endif

        if (depth < cfg.max_depth) {
            name[depth] = elem;
            fvn_depth2(new_hash, depth + 1);
        }
    }
}


// depth of 1 letter (base)
static void fvn_depth0(uint32_t cur_hash) {
    int depth = 0;

    //for (int i = 0; i < MAX_LETTERS; i++) {
    for (int i = cfg.begin_i; i < cfg.end_i; i++) { //slower but ok at this level
        char elem = dict[i];
        if (cfg.print_text)
            printf("- letter: %c\n", elem);

        uint32_t new_hash = cur_hash;
        new_hash += lookup_table[elem];
        new_hash += (new_hash << 10);
        new_hash ^= (new_hash >> 6);

        if (depth < cfg.max_depth) {
            name[depth] = elem;
            fvn_depth1(new_hash, depth + 1);
        }
    }
}


//*************************************************************************

static int get_dict_pos(char comp) {
    // must translate values as banlist works with ASCII
    for (int i = 0; i < MAX_LETTERS; i++) {
        if (dict[i] == comp) {
            return i;
        }
    }

    return -1;
}

static void list_restrict() {
    // overwrite values in list
    if (!cfg.restrict_letters)
        return;
    
    if (cfg.start_letter == '\0')
        cfg.start_letter = 'a';
    if (cfg.end_letter == '\0')
        cfg.end_letter = '9';
    int pos_1 = get_dict_pos(cfg.start_letter);
    int pos_2 = get_dict_pos(cfg.end_letter);
    if (pos_2 < pos_1 || pos_1 < 0 || pos_2 < 0)
        return;

    printf("restricting letters: '%c~%c' %s\n", cfg.start_letter, cfg.end_letter, cfg.restrict_overwrite ? "(overwrite)" : "" );
    for (int i = 0; i < MAX_TABLE; i++) {
        int pos_i = get_dict_pos(i);
        for (int j = 0; j < MAX_TABLE; j++) {
            int pos_j = get_dict_pos(j);
            for (int k = 0; k < MAX_TABLE; k++) {
                int pos_k = get_dict_pos(k);
                if (!(pos_i >= pos_1 && pos_i <= pos_2) ||
                    !(pos_j >= pos_1 && pos_j <= pos_2) ||
                    !(pos_k >= pos_1 && pos_k <= pos_2)) {
                    //printf("ko=[%c][%c][%c] = 0\n", pos_i < 0 ? '*' : dict[pos_i], pos_j < 0 ? '*' : dict[pos_j], pos_k < 0 ? '*' : dict[pos_k]);
                    list3[0][i][j][k] = 0;
                    list3[1][i][j][k] = 0;
                }
                else if (cfg.restrict_overwrite) {
                    //printf("ok=[%c][%c][%c] = 1\n", pos_i < 0 ? '*' : dict[pos_i], pos_j < 0 ? '*' : dict[pos_j], pos_k < 0 ? '*' : dict[pos_k]);
                    list3[0][i][j][k] = 1;
                    list3[1][i][j][k] = 1;
                }
            }
        }
    }

}

static void read_begin_end() {
    int begin = 0;
    int end = MAX_LETTERS;
    
    for (int i = 0; i < MAX_LETTERS; i++) {
        if (dict[i] == cfg.start_letter) {
            begin = i;
        }
        if (dict[i] == cfg.end_letter) {
            end = i + 1;
        }
    }

    cfg.begin_i = begin;
    cfg.end_i = end;
}


static int in_dict(char chr) {
    for (int i = 0; i < MAX_LETTERS; i++) {
        if (dict[i] == chr)
            return 1;
    }

    return 0;
}

static int read_oklist() {
    // 2 ASCII chars = 0x7F | 0x7F, where [char][char] = 0/1, [0] = begin, [1] = middle
    for (int i = 0; i < MAX_TABLE; i++) {
        for (int j = 0; j < MAX_TABLE; j++) {
            for (int k = 0; k < MAX_TABLE; k++) {
                list3[0][i][j][k] = 0;
                list3[1][i][j][k] = 0;
            }
        }
    }

    if (cfg.ignore_banlist)
        return 1;

    FILE* file = fopen(list3_name, "r");
    if (!file) {
        printf("ignore list not found (%s)\n", list3_name);
        return 1;
    }
//printf("2\n");
    char line[0x2000];
    while (fgets(line, sizeof(line), file)) {
        if (line[0] == '#')
            continue;

        int posA = 0;
        int posB = 1;
        int posC = 2;
        int index = 1;
        if (line[0] == '^') {
            posA++;
            posB++;
            posC++;
            index = 0;
        }

        if ( !in_dict(line[posA]) )
            continue;
        if ( !in_dict(line[posB]) )
            continue;
        if ( !in_dict(line[posC]) )
            continue;
        if ( line[posC+1] != ':')
            continue;
        
        int n, m;
        int count;
        m = sscanf(&line[posC+2], "%d%n", &count,&n);
        if (m != 1 || count < 0)
            continue;

        if (count > 0xFF)
            count = 0xFF;
        if (count < cfg.list_threshold)
            count = 0;
        
        list3[index][ (uint8_t)line[posA] ][ (uint8_t)line[posB] ][ (uint8_t)line[posC] ] = count;
        //printf("- %c%c%c: %i\n", line[posA], line[posB], line[posC], count);
    }

    printf("loaded ignore list\n");

    fclose(file);
    return 1;
}

static int read_banlist() {
    // 2 ASCII chars = 0x7F | 0x7F, where [char][char] = 0/1, [0] = begin, [1] = middle
    for (int i = 0; i < MAX_TABLE; i++) {
        for (int j = 0; j < MAX_TABLE; j++) {
            for (int k = 0; k < MAX_TABLE; k++) {
                list3[0][i][j][k] = 1;
                list3[1][i][j][k] = 1;
            }
        }
    }

    //for (int i = 0; i < MAX_LETTERS; i++) {
    //    letters[i] = dict[i];
    //}

    if (cfg.ignore_banlist)
        return 1;

    FILE* file = fopen(list_name, "r");
    if (!file) {
        printf("ignore list not found (%s)\n", list_name);
        return 1;
    }


    char line[0x2000];
    while (fgets(line, sizeof(line), file)) {
        if (line[0] == '#')
            continue;

        int posA = 0;
        int posB = 1;
        int index = 1;
        if (line[0] == '^') {
            posA++;
            posB++;
            index = 0;
        }

        if ( !in_dict(line[posA]) )
            continue;

        if (line[posB] == '[') {
            posB++;
            while( in_dict(line[posB]) ) {
                for (int k = 0; k < MAX_LETTERS; k++) {
                    list3[index][ (uint8_t)line[posA] ][ (uint8_t)line[posB] ][ (uint8_t)dict[k] ] = 0;
                }
                //printf("- %c%c / %i %i\n", line[posA], line[posB], line[posA], line[posB]);
                posB++;
            }
        }
        else if ( in_dict(line[posB]) ) {
            for (int k = 0; k < MAX_LETTERS; k++) {
                list3[index][ (uint8_t)line[posA] ][ (uint8_t)line[posB] ][ (uint8_t)dict[k] ] = 0;
            }
            //printf("- %c%c / %i %i\n", line[posA], line[posB], line[posA], line[posB]);
        }
    }

    printf("loaded ignore list\n");

    fclose(file);
    return 1;
}

//*************************************************************************

static void print_usage(const char* name) {
    fprintf(stderr,"Wwise FNV name reversing tool " FNV_VERSION " " __DATE__ " (%s)\n\n"
            "Finds original name for Wwise event/variable IDs (FNV hashes)\n"
            "Usage: %s [options] (target id)\n"
            "Options:\n"
            "    -p NAME_PREFIX: start text of original name\n"
            "       Use when possible to reduce search space (ex. 'play_')\n"
            "    -s NAME_SUFFIX: end text of original name\n"
            "       Use to reduce search space, but slower than prefix (ex. '_bgm')\n"
            "    -l START_LETTER: start letter (use to resume searches)\n"
            "    -L END_LETTER: end letter\n"
            "       Dictionary letters: %s\n"
            "    -r: restrict START/END letters to all levels (uses ignore list combos)\n"
            "    -R: restrict START/END letters to all levels (overwrites ignore list combos)\n"
            "    -X x: restrict START/END letters to all levels, where x is a letter:\n"
            "         a=a..z_; A=a..z; n=_..9; N=0..9\n"
            "    -m N: max characters in name (default %i)\n"
            "       Beyond 8 search is slow and gives many false positives (may improve with -I)\n"
            "    -I THRESHOLD: enable allowed 3-gram lists, at threshold N\n"
            "    -i: ignore ban list (%s)\n"
            "       List greatly improves speed and results but may skip valid names\n"
            "       (try disabling if no proper names are found for smaller variables)\n"
            "    -t: print letter text info (when using high max characters)\n"
            "    -n: treat input as names and prints FNV IDs (32-bit)\n"
            "    -h: show this help\n"
            ,
            (sizeof(void*) >= 8 ? "64-bit" : "32-bit"),
            name,
            dict,
            default_depth,
            list_name);
}


#define CHECK_EXIT(condition, ...) \
    do {if (condition) { \
       fprintf(stderr, __VA_ARGS__); \
       return 0; \
    } } while (0)

static int parse_cfg(fnv_config* cfg, int argc, const char* argv[]) {
    cfg->max_depth = default_depth;
    
    for (int i = 1; i < argc; i++) {

        if (argv[i][0] != '-') {
            cfg->targets_s[cfg->targets_count] = argv[i];
            cfg->targets_count++;

            CHECK_EXIT(cfg->targets_count >= MAX_TARGETS, "ERROR: too many targets");
            continue;
        }

        switch(argv[i][1]) {
            case 'p':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing name prefix");
                strncpy(cfg->name_prefix, argv[i], MAX_CHARS);
                cfg->name_prefix_len = strlen(cfg->name_prefix);
                break;
            case 's':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing name suffix");
                strncpy(cfg->name_suffix, argv[i], MAX_CHARS);
                cfg->name_suffix_len = strlen(cfg->name_suffix);
                break;
            case 'l':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing start letter");
                CHECK_EXIT(strlen(argv[i]) > 1, "ERROR: start letter must be 1 character");
                cfg->start_letter = tolower(argv[i][0]);
                break;
            case 'L':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing end letter");
                CHECK_EXIT(strlen(argv[i]) > 1, "ERROR: end letter must be 1 character");
                cfg->end_letter = tolower(argv[i][0]);
                break;
            case 'i':
                cfg->ignore_banlist = 1;
                break;
            case 'I':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing max characters");
                cfg->read_oklist = 1;
                cfg->list_threshold = strtoul(argv[i], NULL, 10);
                break;
            case 't':
                cfg->print_text = 1;
                break;
            case 'm':
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing max characters");
                cfg->max_depth = strtoul(argv[i], NULL, 10);
                break;
            case 'n':
                cfg->reverse_names = 1;
                break;
            case 'r':
                cfg->restrict_letters = 1;
                break;
            case 'R':
                cfg->restrict_letters = 1;
                cfg->restrict_overwrite = 1;
                break;
            case 'X':
                cfg->restrict_letters = 1;
                i++;
                CHECK_EXIT(i >= argc, "ERROR: missing max characters");
                switch(argv[i][0]) {
                    case 'a':
                        cfg->start_letter = 'a';
                        cfg->end_letter = '_';
                        break;
                    case 'A':
                        cfg->start_letter = 'a';
                        cfg->end_letter = 'z';
                        break;
                    case 'n':
                        cfg->restrict_overwrite = 1;
                        cfg->start_letter = '_';
                        cfg->end_letter = '9';
                        break;
                    case 'N':
                        cfg->restrict_overwrite = 1;
                        cfg->start_letter = '0';
                        cfg->end_letter = '9';
                        break;
                    default:
                        break;
                }
                break;
            case 'h':
                print_usage(argv[0]);
                return 0;
            default:
                CHECK_EXIT(1, "ERROR: unknown parameter '%s'\n", argv[i]);
                break;
        }
    }


    CHECK_EXIT(cfg->max_depth < 0, "ERROR: too few letters\n");
    CHECK_EXIT(cfg->max_depth >= MAX_DEPTH, "ERROR: too many letters\n");
    CHECK_EXIT(cfg->max_depth >= MAX_DEPTH, "too many letters\n");
    CHECK_EXIT(cfg->targets_count <= 0, "ERROR: target ids not specified\n");

    if (!cfg->reverse_names) {
        for (int i = 0; i < cfg->targets_count; i++) {
            const char* name = cfg->targets_s[i];

            uint32_t target = strtoul(name, NULL, 10);
            cfg->targets[i] = target;

            CHECK_EXIT(target == 0, "ERROR: incorrect value for target");
        }
    }

    if (cfg->name_prefix_len) {
        for (int i = 0; i < cfg->name_prefix_len; i++) {
            cfg->name_prefix[i] = tolower(cfg->name_prefix[i]);
        }
    }

    if (cfg->name_suffix_len) {
        for (int i = 0; i < cfg->name_suffix_len; i++) {
            cfg->name_suffix[i] = tolower(cfg->name_suffix[i]);
        }
    }
    
    read_begin_end();
    
    return 1;
}    

static void print_time(const char* info) {
    time_t timer;
    struct tm* tm_info;

    timer = time(NULL);
    tm_info = localtime(&timer);
    printf("%s: %s", info, asctime(tm_info));
}

static void reverse_names(fnv_config* cfg) {
    for (int t = 0; t < cfg->targets_count; t++) {
        const char* name = cfg->targets_s[t];

        uint32_t hash = 2166136261;
        for (int i = 0; i < strlen(name); i++) {
            char c = tolower(name[i]);
            hash = (hash * 16777619) ^ (uint8_t)c;
        }

#if 0
        if (cfg->reverse_names_30b) {
            uint32_t mask = (1U << 30) - 1;
            hash = (hash >> 30) ^ (mask & hash);
        }
#endif

        printf("%s: %u / 0x%x\n", name, hash, hash);
        //printf("%u: \"%s\",\n", hash, name);
    }
}

int main(int argc, const char* argv[]) {
    if (argc <= 1) {
        print_usage(argv[0]);
        return 1;
    }

    if (!parse_cfg(&cfg, argc, argv)) {
        return 1;
    }

    if (cfg.reverse_names) {
        reverse_names(&cfg);
        return 0;
    }

    if (cfg.read_oklist) {
        if (!read_oklist()) {
            return 1;
        }
    }
    else {
        if (!read_banlist()) {
            return 1;
        }
    }
    list_restrict();


    cfg.max_depth--;
    cfg.max_depth_1 = cfg.max_depth - 1;

    printf("starting, max %i letters\n", cfg.max_depth + 1);
    printf("\n");

    uint32_t base_hash = 0;
    if (cfg.name_prefix_len) {
        for (int i = 0; i < cfg.name_prefix_len; i++) {
            base_hash = (base_hash * 16777619) ^ cfg.name_prefix[i];
        }
    }

    print_time("start");
    for (int t = 0; t < cfg.targets_count; t++) {
        cfg.target = cfg.targets[t];

        printf("finding %u\n", cfg.target);

        // with a suffix we can undo last N steps of target
        if (cfg.name_suffix_len) {
            cfg.target = ifnv_target(cfg.target, cfg.name_suffix, cfg.name_suffix_len);
        }

        // check base (that includes prefix and suffix) first just in case
        if (base_hash == cfg.target) {
            print_name(-1);
        }

        fvn_depth0(base_hash);

        printf("\n");
    }
    print_time("end");


    return 0;
}
