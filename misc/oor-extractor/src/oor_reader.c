/* Handles .oor packets.
 * Format is bitpacked and some parts may be ambiguous, but it should fail midway on bad data.
 *
 * Info from:
 * - mostly https://github.com/tsudoko/deoptimizeobs (FORMAT doc describes it, but some info is slightly off)
 * - some bits from decompilation
*/

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <math.h>
#include "bitstream_msb.h"

#define OOR_FLAG_CONTINUED      (1<<3)  // 1000 = continued (first packet in page is part of last; equivalent to OggS 0x01)
#define OOR_FLAG_PARTIAL        (1<<2)  // 0100 = partial (last packet in page is not complete and must be merged with prev; OggS uses size 0xFF for this)
#define OOR_FLAG_BOS            (1<<1)  // 0010 = beginning-of-stream (irst page, OggS 0x02)
#define OOR_FLAG_EOS            (1<<0)  // 0001 = end-of-stream (last page, OggS 0x04)
//#define OOR_FLAG_NORMAL       0       // any other regular packet


typedef struct {
    uint8_t version;
    uint8_t flags;
    int64_t granule;
    int padding1;
    int padding2;
} oor_page_t;

typedef struct {
    uint8_t vps_bits;
    uint8_t padding1;
    uint8_t packet_count;
    uint8_t bps_selector;
    int16_t base_packet_size; // max 7FF (may be 0)
    int16_t variable_packet_size[256]; // max 7FFF of N packet_count (may be 0)
    uint8_t post_padding;
} oor_size_t;

typedef struct {
    uint8_t pre_padding;
    uint8_t version;
    uint8_t channels;
    int sample_rate;
    uint8_t unknown1;
    uint8_t unknown2;
    uint8_t unknown3;
    int64_t last_granule;
    uint8_t blocksize0_exp;
    uint8_t blocksize1_exp;
    uint8_t framing;
    uint8_t post_padding;
} oor_header_t;

// codebooks are set in plugin with a table of size + codebook
typedef struct {
    int type;
    int codebook_id;
} oor_setup_t;


// .oor is divided into pages like "OggS", but simplified (variable sized)
// - v0: 0x01
// - v1: 0x0A
static void read_oor_page(bitstream_t* is, oor_page_t* page) {
    uint32_t granule_hi = 0, granule_lo = 0; //bitreader only handles 32b

    page->version    = bm_read(is, 2);
    page->flags      = bm_read(is, 4); // vorbis packet flags

    // extra fields in V1
    switch(page->version) {
        case 0:
            page->granule  = 0;
            page->padding1 = 0;
            page->padding2 = 0;
            // bitstream ends with into bit 6 of current byte
            break;

        case 1:
            page->padding1  = bm_read(is, 2); // padding as granule must be byte-aligned
            granule_hi      = bm_read(is, 32);
            granule_lo      = bm_read(is, 32);
            page->granule   = ((uint64_t)granule_hi << 32) | granule_lo;
            page->padding2  = bm_read(is, 6); // padding to leave bitstream into bit 6, like v0
            break;
        
        default: // unknown version
            break;
    }
}

// each .oor page except the first (header) has N packets:
// size is variable but theoretical max is ~0x200 (plus page header)
static void read_oor_size(bitstream_t* is, oor_size_t* size) {
    // right after page info (meaning 6 bits into bitstream)
    size->vps_bits      = bm_read(is, 4);
    size->padding1      = bm_read(is, 1);
    size->packet_count  = bm_read(is, 8);
    size->bps_selector  = bm_read(is, 2);

    switch(size->bps_selector) {
        case 0: size->base_packet_size = 0; break; // 0 bits
        case 1: size->base_packet_size = bm_read(is, 8); break;
        case 2: size->base_packet_size = bm_read(is, 11); break;
        case 3: //undefined
        default: 
            size->base_packet_size = 0;
            break;
    }

    for (int i = 0; i < size->packet_count; i++) {
        if (size->vps_bits) {
            size->variable_packet_size[i] = bm_read(is, size->vps_bits);
        }
        else {
            size->variable_packet_size[i] = 0; //reset in case of reusing struct
        }
    }

    uint32_t bit_pos = bm_pos(is) % 8;
    if (bit_pos > 0) {
        size->post_padding = bm_read(is, 8 - bit_pos); // aligned to next byte
    }
    else {
        size->post_padding = 0;
    }

    // bitstream is now byte-aligned, and next is N packets of base + variable packet sizes (in bytes)
}

// bit-packed header (variable-sized):
// - v0 (sr_selector!=3): 0x02
// - v0 (sr_selector==3): 0x03
// - v1 (sr_selector!=3): 0x12
// - v1 (sr_selector==3): 0x13
static void read_oor_header(bitstream_t* is, oor_header_t* hdr) {
    hdr->pre_padding    = bm_read(is, 2); // from first page, header is byte-aligned

    hdr->version        = bm_read(is, 2);
    hdr->channels       = bm_read(is, 3);
    int sr_selector     = bm_read(is, 2);

    if (sr_selector == 3) {
        int sr_index    = bm_read(is, 8);

        // few known modes, though they have 8 bits
        // seems v1 lib can handle v0 files but sample rate is not compatible, maybe an oversight
        // (note that some games somehow have both v0 and v1 files)
        switch(hdr->version) {
            case 0:
                switch(sr_index) {
                    case 3: hdr->sample_rate = 32000; break;
                    case 4: hdr->sample_rate = 48000; break;
                    case 5: hdr->sample_rate = 96000; break;
                    default: hdr->sample_rate = 0; break;
                }

            case 1:
                switch(sr_index) {
                    case 4: hdr->sample_rate = 32000; break;
                    case 5: hdr->sample_rate = 48000; break;
                    case 6: hdr->sample_rate = 64000; break;
                    case 7: hdr->sample_rate = 88200; break;
                    case 8: hdr->sample_rate = 96000; break;
                    default: hdr->sample_rate = 0; break;
                }
                break;

            default:
                break;
        }

        // shouldn't happen, but allow to catch missing cases
        if (hdr->sample_rate == 0) // && sr_index < 256
            hdr->sample_rate = 8000;
    }
    else {
        hdr->sample_rate = 11025 * pow(2, sr_selector);
    }

    if (hdr->version == 1) {
        uint32_t granule_hi = 0, granule_lo = 0; //bitreader only handles 32b

        hdr->unknown1   = bm_read(is, 1); // always 1?
        hdr->unknown2   = bm_read(is, 1); // always 1?
        hdr->unknown3   = bm_read(is, 7); // always 0?

        granule_hi      = bm_read(is, 32);
        granule_lo      = bm_read(is, 32);
        hdr->last_granule = ((uint64_t)granule_hi << 32) | granule_lo;
    }
    else {
        hdr->unknown1   = 0;
        hdr->unknown2   = 0;
        hdr->unknown3   = 0;
        hdr->last_granule = 0;
    }

    hdr->blocksize1_exp  = bm_read(is, 4);
    hdr->blocksize0_exp  = bm_read(is, 4);
    hdr->framing         = bm_read(is, 1); //always 1

    uint32_t bit_pos = bm_pos(is) % 8;
    if (bit_pos > 0) {
        hdr->post_padding = bm_read(is, 8 - bit_pos); // aligned to next byte
    }
    else {
        hdr->post_padding = 0;
    }
}

// bit-packed setup (should be byte-aligned)
static void read_oor_setup(bitstream_t* is, oor_setup_t* setup) {
    setup->type         = bm_read(is, 2);
    setup->codebook_id  = bm_read(is, 6);
    // known codebooks:
    // 1~6: early
    // 7: ~2016 (Steam/Vita ports)
}

// extra validations since bitpacket headers are a bit simple
static bool validate_header_page(oor_page_t* page, oor_header_t* hdr) {
    if (page->version > 1 || page->flags != 0x02)
        return false;

    if (page->granule != 0 || page->padding1 != 0 || page->padding2 != 0)
        return false;

    if (hdr->pre_padding != 0 || hdr->version > 1 || hdr->version != page->version)
        return false;
    if (hdr->channels == 0 || hdr->sample_rate == 0)
        return false;
    //if (hdr->channels > OOR_MAX_CHANNELS) // known max is 2, allow to detect other cases
    //    return false;

    if (hdr->version == 1 && hdr->last_granule == 0)
        return false;

    if (hdr->blocksize0_exp < 6 || hdr->blocksize0_exp > 13 || hdr->blocksize1_exp < 6 || hdr->blocksize1_exp > 13)
        return false;
    if (hdr->framing != 1)
        return false;

    if (hdr->post_padding != 0)
        return false;

    return true;
}

static bool validate_setup_page(oor_page_t* page, oor_size_t* size, oor_header_t* hdr) {
    if (page->version != hdr->version)
        return false;
    // oddly enough codebooks may be split into other pages using OOR_FLAG_PARTIAL
    if (page->flags & OOR_FLAG_CONTINUED || page->flags & OOR_FLAG_BOS || page->flags & OOR_FLAG_EOS)
        return false;

    if (page->granule != 0 || page->padding1 != 0 || page->padding2 != 0)
        return false;
    if (size->padding1 != 0 || size->bps_selector == 3)
        return false;
    if (size->post_padding != 0)
        return false;

    //if (setup->type != 0x01)
    //    return false;
    //if (setup->codebook_id > OOR_MAX_CODEBOOK_ID) // known max is 7, allow to detect other cases
    //    return false;

    return true;
}

static bool validate_setup_info(oor_page_t* page, oor_size_t* size, oor_setup_t* setup) {

    // setup packet always has 2 packets: setup info + vorbis codebook
    if (size->packet_count != 2)
        return false;
    int packet0_size = size->base_packet_size + size->variable_packet_size[0];
    int packet1_size = size->base_packet_size + size->variable_packet_size[1];

    if (packet0_size != 0x01)
        return false;
    // size is 0 when using codebook ids
    if ((setup->codebook_id > 0 && packet1_size != 0) || (setup->codebook_id == 0 && packet1_size == 0))
        return false;
    return true;
}

static bool validate_audio_page(oor_page_t* page, oor_size_t* size, oor_header_t* hdr) {
    if (hdr != NULL && page->version != hdr->version)
        return false;
    if (page->flags & OOR_FLAG_BOS)
        return false;
    if (page->padding1 != 0 || page->padding2 != 0)
        return false;

    if (size->padding1 != 0 || size->bps_selector == 3)
        return false;
    if (size->post_padding != 0)
        return false;

    if (size->packet_count == 0)
        return false;
    // packet size may be 0 in rare cases, but packet count should be 1 at least

    return true;
}

// reads .oor data until end of stream flag; returns size (ok), 0 (wrong) or negative (odd cases)
int read_oor(uint8_t* buf, uint32_t left) {
    oor_page_t page = {0};
    oor_size_t size = {0};
    oor_header_t hdr = {0};
    oor_setup_t setup = {0};

    // bitreader only handles 32b but .oor files should never reach this
    if (left >= 0x1FFFFFFF)
        left = 0x1FFFFFFF;

    bitstream_t is_tmp;
    bitstream_t* is = &is_tmp;
    bm_setup(is, buf, left);

    // header page
    read_oor_page(is, &page);
    read_oor_header(is, &hdr);
    if (!validate_header_page(&page, &hdr))
        return 0;

    // setup page
    read_oor_page(is, &page);
    read_oor_size(is, &size);
    if (!validate_setup_page(&page, &size, &hdr))
        return 0;

    read_oor_setup(is, &setup); // considered 1st packet but should always go after size
    if (!validate_setup_info(&page, &size, &setup))
        return 0;

    uint32_t codebook_size = size.base_packet_size + size.variable_packet_size[1];
    bm_skip(is, codebook_size * 8);

    while (true) {
        if (is->b_off >= is->b_max) {
            return -(bm_pos(is) / 8);
        }

        read_oor_page(is, &page);
        read_oor_size(is, &size);

        if (!validate_audio_page(&page, &size, &hdr)) {
            return -(bm_pos(is) / 8);
        }

        for (int i = 0; i < size.packet_count; i++) {
            int packet_size = size.base_packet_size + size.variable_packet_size[i];
            bm_skip(is, packet_size * 8);        
        }

        // end found
        if (page.flags & (1<<0))
            break;
    }

    // bm_pos should be already aligned
    uint32_t final_size = bm_pos(is) / 8;
    //printf("final_size=%x\n", final_size);

    return final_size;
}

// print info to detect new .oor variations
bool check_oor(uint8_t* buf, uint32_t left) {
    oor_page_t page = {0};
    oor_size_t size = {0};
    oor_header_t hdr = {0};
    oor_setup_t setup = {0};

    // bitreader only handles 32b but .oor files should never reach this
    if (left >= 0x1FFFFFFF)
        left = 0x1FFFFFFF;

    bitstream_t is_tmp;
    bitstream_t* is = &is_tmp;
    bm_setup(is, buf, left);

    // header page
    read_oor_page(is, &page);
    read_oor_header(is, &hdr);
    if (!validate_header_page(&page, &hdr))
        return false;

    // setup page
    read_oor_page(is, &page);
    read_oor_size(is, &size);
    if (!validate_setup_page(&page, &size, &hdr))
        return false;

    read_oor_setup(is, &setup); // considered 1st packet but should always go after size
    if (!validate_setup_info(&page, &size, &setup))
        return false;

    uint32_t codebook_size = size.base_packet_size + size.variable_packet_size[1];
    bm_skip(is, codebook_size * 8);



    /* actual checks */
    if (hdr.sample_rate == 8000 || hdr.channels > 2) {
        printf("- unknown header found: ch=%i, srate=%i (report)\n", hdr.channels, hdr.sample_rate);
        return false;
    }

    if (hdr.version == 1 && (hdr.unknown1 != 1 || hdr.unknown2 != 1 || hdr.unknown3 != 0)) {
        printf("- unknown flags found: u1=%i, u2=%i, u3=%i (report)\n", hdr.unknown1, hdr.unknown2, hdr.unknown3);
        return false;
    }

    if (setup.codebook_id > 7) {
        printf("- unknown codebook found: id=%i (report)\n", setup.codebook_id);
        return false;
    }

    if (setup.type > 6) {
        printf("- unknown setup type found: type=%i (report)\n", setup.type);
        return false;
    }

    if (size.packet_count != 2) {
        printf("- unknown setup count: count=%i (report)\n", size.packet_count);
        return false;
    }

    return true;
}


#ifdef READER_MAIN
int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "Usage: %s <input file>\n", argv[0]);
        return 1;
    }

    printf("processing: %s\n", argv[1]);
    FILE *input_file = fopen(argv[1], "rb");
    if (!input_file) {
        perror("Failed to open input file");
        return 1;
    }

    fseek(input_file, 0, SEEK_END);
    long file_size = ftell(input_file);
    fseek(input_file, 0, SEEK_SET);

    unsigned char* buffer = malloc(file_size);
    if (!buffer) {
        fprintf(stderr, "Failed to allocate memory\n");
        fclose(input_file);
        return 1;
    }

    int bytes = fread(buffer, 1, file_size, input_file);
    if (bytes != file_size) {
        printf("could't read fully\n");
    }
    else {
        printf("size: %x\n", bytes);
        read_oor(buffer, file_size);
    }


    free(buffer);
    fclose(input_file);

    printf("done.\n");
    return 0;
}
#endif
