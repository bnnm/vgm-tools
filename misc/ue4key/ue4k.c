// UE4KEYFINDER
// Dumb test key finder for encrypted .pak for learning purposes,
// surely there are better programs out there.

#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <ctype.h>

// make sure to pass these compiler flags or change aes.h:
//#define AES256 1
//#define CBC 0
//#define ECB 1
//#define CTR 0
#include "aes.h"

#define UE4_TOC_MAGIC  0x5A6F12E1
#define MAX_ZEROES 2

// make sure bigfiles work, not sure which is better
//#define ue4_ftell ftello       //GCC
//#define ue4_fseek fseeko       //GCC
#define ue4_ftell ftello64     //GCC
#define ue4_fseek fseeko64     //GCC
#define ue4_fopen fopen64     //GCC
//#define ue4_ftello _ftelli64    //MSVC
//#define ue4_fseeko _fseeki64    //MSVC
//#define ue4_fopen _fopen64     //MSVC?


typedef struct {
    const char* pak_name;
    const char* key_name;
    int debug;
    
    FILE* out;

} pak_config;

pak_config cfg;
const int key_size = 32;
uint8_t buf[16];


static void write_out(const uint8_t* key) {
    char line[0x100];
    
    //TODO ?
    snprintf(line, sizeof(line), " possible key:\n  0x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x%02x\n", 
        key[0x00], key[0x01], key[0x02], key[0x03], key[0x04], key[0x05], key[0x06], key[0x07], 
        key[0x08], key[0x09], key[0x0a], key[0x0b], key[0x0c], key[0x0d], key[0x0e], key[0x0f],
        key[0x10], key[0x11], key[0x12], key[0x13], key[0x14], key[0x15], key[0x16], key[0x17], 
        key[0x18], key[0x19], key[0x1a], key[0x1b], key[0x1c], key[0x1d], key[0x1e], key[0x1f]
    );

    printf("%s", line);

    if (!cfg.out) {
        cfg.out = ue4_fopen("keys.txt", "a");
        if (!cfg.out) {
            printf("can't open keys.txt");
            return;
        }

        char header[0x1000];
        snprintf(header, sizeof(header), "finding keys for %s in %s\n", cfg.pak_name, cfg.key_name);
        fwrite(header, sizeof(char), strlen(header), cfg.out);
    }

    fwrite(line, sizeof(char), strlen(line), cfg.out);
}

static int is_bad(uint8_t* test) {
    int count = 0;
    for (int i = 0; i < 8; i++) {
        if (test[i] == 0) {
            count++;
            if (count > MAX_ZEROES)
                return 1;
        }
    }
    
    return 0;
}

// decrypted TOC must be:
//  00 text size
//  04 text + null terminator (included)
//  NN data
static int is_probable_key(uint8_t* dec) {
    int text_size = dec[0];
    if (text_size > key_size - 4)
        text_size = key_size - 4;

    if (text_size < 1) {
        return 0;
    }

    // text must be ascii
    for (int k = 4; k < 4 + text_size - 1; k++) {
        if (dec[k] < 0x20 || dec[k] > 0x80) {
            return 0;
        }
    }

    // string ends with (if text doesn't go past first block)
    if (text_size < key_size - 4) {
        if (dec[4 + text_size - 1] != 0) {
            return 0;
        }
    }

    return 1;
}

static int test_key() {
    FILE* file = ue4_fopen(cfg.key_name, "rb");
    if (!file) {
        printf("keys not found: %s\n", cfg.key_name);
        return 1;
    }

    size_t max = 0x200000;
    uint8_t* test = malloc(max);
    if (!test) {
        printf("bad key\n");
        return 0;
    }

    ue4_fseek(file, 0, SEEK_END);
    size_t offset_max = ue4_ftell(file);
    size_t offset = 0;
    ue4_fseek(file, 0, SEEK_SET);

    struct AES_ctx ctx = {0};
    uint8_t dec[16];


    while (offset < offset_max) {
        if (cfg.debug)
            printf("offset: %08x\n", ue4_ftell(file));

        fread(test, sizeof(char), max, file);
        offset = ue4_ftell(file);

        for (int i = 0; i < max - key_size; i++) {
            if (is_bad(test+i)) {
                continue;
            }

            memcpy(dec, buf, sizeof(buf));
            // decrypt TOC
            AES_init_ctx(&ctx, test+i);
            AES_ECB_decrypt(&ctx, dec);

            if (dec[1] == 0 && dec[2] == 0 && dec[3] == 0) {
                if (!is_probable_key(dec))
                    continue;
                write_out(test+i);
            }
        }

        ue4_fseek(file, -key_size, SEEK_CUR);
    }

    fclose(file);
    return 0;
}

static uint32_t get_u32be(const uint8_t* p) {
    return (uint32_t)(p[0]<<24) | (p[1]<<16) | (p[2]<<8) | (p[3]);
}

static uint32_t get_u32le(const uint8_t* p) {
    return (uint32_t)(p[0]) | (p[1]<<8) | (p[2]<<16) | (p[3]<<24);
}

static int read_pck() {
    FILE* file = ue4_fopen(cfg.pak_name, "rb");
    if (!file) {
        printf("pak not found: %s\n", cfg.pak_name);
        return 1;
    }

    uint8_t test[0x1000];

    //ue4_fseek(file, -sizeof(test), SEEK_END); //KO
    ue4_fseek(file, 0, SEEK_END);
    off_t file_size = ue4_ftell(file);
    ue4_fseek(file, file_size - sizeof(test), SEEK_SET);
    
    
    size_t bytes = fread(test, sizeof(uint8_t), sizeof(test), file);
    if (bytes != sizeof(test)) {
        printf("can't read file: read=%x, expected=%x\n", bytes, sizeof(test));
        goto fail;
    }

    for (int i = 0; i < sizeof(test) - 4; i++) {
        uint32_t value = get_u32le(test+i);

        if (value == UE4_TOC_MAGIC) {
            uint32_t offset = get_u32le(test+i+8);
            ue4_fseek(file, offset, SEEK_SET);

            bytes = fread(buf, sizeof(uint8_t), sizeof(buf), file);
            if (bytes != sizeof(buf)) {
                printf("can't read TOC: read=%x, expected=%x\n", bytes, sizeof(buf));
                goto fail;
            }

            fclose(file);
            return 1;
        }
    }

    printf("error, PAK table of contents not found\n");
fail:
    fclose(file);
    return 0;
}

//*************************************************************************

static void print_usage(const char* name) {
    fprintf(stderr,"UE4 key finder " __DATE__ "\n\n"
            "Finds encryption keys given a binary file (exe, memdumps) + .pak\n"
            "Usage: %s [options] (file.pak)\n"
            "Options:\n"
            "    -k KEY_FILE: file where keys are\n"
            "       Defaults to keys.bin\n"
            "    -d: debug output\n"
            ,
            name);
}


#define CHECK_EXIT(condition, ...) \
    do {if (condition) { \
       fprintf(stderr, __VA_ARGS__); \
       return 0; \
    } } while (0)

static int parse_cfg(pak_config* cfg, int argc, const char* argv[]) {
    for (int i = 1; i < argc; i++) {

        if (argv[i][0] != '-') {
            cfg->pak_name = argv[i];
            continue;
        }

        switch(argv[i][1]) {
            case 'k':
                i++;
                cfg->key_name = argv[i];
                break;
            case 'd':
                cfg->debug = 1;
                break;
            default:
                CHECK_EXIT(1, "ERROR: unknown parameter '%s'\n", argv[i]);
                break;
        }
    }

    if (!cfg->key_name) {
        cfg->key_name = "keys.bin";
    }
    
    
    return 1;
}    

static void print_time(const char* info) {
    time_t timer;
    struct tm* tm_info;

    timer = time(NULL);
    tm_info = localtime(&timer);
    printf("%s: %s", info, asctime(tm_info));
}

int main(int argc, const char* argv[]) {
    if (argc <= 1) {
        print_usage(argv[0]);
        return 1;
    }

    if (!parse_cfg(&cfg, argc, argv)) {
        return 1;
    }

    if (!read_pck()) {
        return 1;
    }

    print_time("start");
    test_key();
    print_time("end");

    if (cfg.out)
        fclose(cfg.out);

    return 0;
}
