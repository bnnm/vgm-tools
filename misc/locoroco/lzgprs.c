#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

//#define SEXT14(x) ( (x & 0x80) ? (0xFFFFFF00 | x) : x )
#define SEXT14(x) (x)

/* LZGPRS by bnnm - decompresses custom LZ from LocoRoco GRPS files */

/* Reverse engineered from the ELF with Ghidra + PSP loader and barely cleaned up.
 * (see https://github.com/kotcrab/ghidra-allegrex)
 * 
 * There is also a chunked version for files >0x10000 where it freads malloc'd
 * 0x10000 chunks when src is consumed but this works for whole files too) */
static void decompress_lzgprs(uint8_t* dst, size_t dst_size, const uint8_t* src, size_t src_size)  {
    uint8_t* dst_end = dst + dst_size;
    const uint8_t* src_end = src + src_size;

    uint8_t flags;
    uint8_t flags_tmp;
    uint8_t cur; //uint32_t cur;
    uint32_t test;
    uint32_t test_tmp;
    uint32_t test2;
    const uint8_t *src_next;
    int count;

    cur = SEXT14(*src);
    flags = 0x80;
    src = src + 1;
    do {
        while( 1 ) {
            if (flags == 0) {
                cur = SEXT14(*src);
                flags = 0x80;
                src_next = src + 1;
                test = cur & 0x80;
            }
            else {
                test = cur & flags;
                src_next = src;
            }
            flags = (int)flags >> 1;
            if (test != 0) break;
            *dst = *src_next;
            src = src_next + 1;
            dst = dst + 1;
        }

        if (flags == 0) {
            cur = SEXT14(*src_next);
            flags = 0x80;
            src_next = src_next + 1;
            test = cur & 0x80;
        }
        else {
            test = cur & flags;
        }
        
        flags = (int)flags >> 1;
        if (test == 0) {
            src = src_next + 1;
            if ((int)*src_next == 0) {
                return;
            }
            test = (int)*src_next | 0xffffff00;
        }
        else {
            src = src_next + 1;
            if (flags == 0) {
                cur = SEXT14(*src);
                flags = 0x80;
                src = src_next + 2;
            }
            
            test = cur & flags;
            flags = (int)flags >> 1;
            if (flags == 0) {
                cur = SEXT14(*src);
                flags = 0x80;
                src = src + 1;
            }
            
            test2 = cur & flags;
            flags = (int)flags >> 1;
            if (flags == 0) {
                cur = SEXT14(*src);
                flags = 0x80;
                src = src + 1;
            }
            
            test_tmp = cur & flags;
            flags_tmp = (int)flags >> 1;
            if (flags_tmp == 0) {
                cur = SEXT14(*src);
                flags_tmp = 0x80;
                src = src + 1;
            }
            
            flags = (int)flags_tmp >> 1;
            test = 
                (((((
                    (int)*src_next | 0xffffff00U) * 2 + 
                    (uint32_t)(test != 0)) * 2 + 
                    (uint32_t)(test2 != 0)) * 2 + 
                    (uint32_t)(test_tmp != 0)) * 2 + 
                    (uint32_t)((cur & flags_tmp) != 0)) - 0xff;
        }

        count = 1;
        while( 1 ) {
            if (flags == 0) {
                cur = SEXT14(*src);
                flags = 0x80;
                src = src + 1;
                test2 = cur & 0x80;
            }
            else {
                test2 = cur & flags;
            }
            
            flags = (int)flags >> 1;
            if (test2 == 0) break;
            if (flags == 0) {
                cur = SEXT14(*src);
                flags = 0x80;
                src = src + 1;
                test2 = cur & 0x80;
            }
            else {
                test2 = cur & flags;
            }
            flags = (int)flags >> 1;
            count = count * 2 + (uint32_t)(test2 != 0);
        }
        
        if (count < 7) {
            while (-1 < count) {
                count = count + -1;
                *dst = dst[test];
                dst = dst + 1;
            }
        }
        else {
            test2 = (count + 1U) & 7;
            count = (int)(count + 1U) >> 3;
            dst = dst + (test2 - 8);
            src_next = dst + test;
            switch(test2) {
            case 0:
                while( 1 ) {
                    count = count + -1;
                    dst = dst + 8;
                    src_next = src_next + 8;
                    if (count < 0) break;
                    switchD_00043094_caseD_8:
                    *dst = *src_next;
                    switchD_00043094_caseD_7:
                    dst[1] = src_next[1];
                    switchD_00043094_caseD_6:
                    dst[2] = src_next[2];
                    switchD_00043094_caseD_5:
                    dst[3] = src_next[3];
                    switchD_00043094_caseD_4:
                    dst[4] = src_next[4];
                    switchD_00043094_caseD_3:
                    dst[5] = src_next[5];
                    switchD_00043094_caseD_2:
                    dst[6] = src_next[6];
                    switchD_00043094_caseD_1:
                    dst[7] = src_next[7];
                }
                break;
            case 1:
                goto switchD_00043094_caseD_1;
            case 2:
                goto switchD_00043094_caseD_2;
            case 3:
                goto switchD_00043094_caseD_3;
            case 4:
                goto switchD_00043094_caseD_4;
            case 5:
                goto switchD_00043094_caseD_5;
            case 6:
                goto switchD_00043094_caseD_6;
            case 7:
                goto switchD_00043094_caseD_7;
            default:
                goto switchD_00043094_caseD_8;
            }
        }
    }
    while (src < src_end && dst < dst_end);

}

uint32_t read_i32be(FILE *f, off_t offset) {
    uint8_t buf[4];
    fseek(f, offset, SEEK_SET);
    fread(buf, 1, 4, f);
    
    return (buf[3] << 0) | (buf[2] << 8u) | (buf[1] << 16u) | (buf[0] << 24u);
}


int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("LZGPRS decompressor for LocoRoco by bnnm\nUsage: %s infile\n", argv[0]);
        return 1;
    }

    FILE* f_out = NULL;
    FILE* f_in = NULL;
    uint8_t *src = NULL;
    uint8_t *dst = NULL;

    f_in = fopen(argv[1], "rb");
    if (f_in == NULL) {
        printf("cannot open infile %s", argv[1]);
        goto end;
    }

    char s_out[32768];
    strcpy(s_out, argv[1]);
    strcat(s_out, ".dec");
    f_out = fopen(s_out, "wb");
    if (f_out == NULL) {
        printf("cannot open outfile %s", s_out);
        goto end;
    }

    fseek(f_in, 0, SEEK_END);
    size_t src_size = ftell(f_in);

    uint32_t grps_id = read_i32be(f_in, 0x00);
    if (grps_id != 0x47505253) {
        printf("not a GPRS open file %s", argv[1]);
        goto end;
    }
    size_t dst_size = read_i32be(f_in, 0x04);

    if (src_size > 0x10000000 || dst_size > 0x10000000) {
        printf("bad sizes\n");
        goto end;
    }
    
    src = malloc(src_size);
    dst = calloc(dst_size, 1);
    if (!src || !dst) {
        printf("bad alloc\n");
        goto end;
    }

    fseek(f_in, 0x08, SEEK_SET);
    fread(src, 1, src_size, f_in);

    decompress_lzgprs(dst, dst_size, src, src_size);
    fwrite(dst, sizeof(char), dst_size, f_out);    
    
    //printf("done (input=%x, output=%x)\n", src_size, dst_size);

end:
    free(src);
    free(dst);
    fclose(f_in);
    fclose(f_out);
    return 0;
}
