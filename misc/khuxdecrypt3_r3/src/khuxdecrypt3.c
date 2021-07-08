/* KHUX BGAD EXTRACTOR
 * v1 2016 by GovanifY
 * v2 by ?
 * v3 2020-02-20 by bnnm
 * - restructured/redone, more options, stuff
 * - decrypts KHUX newer files and handles split files (misc.mp4.1)
 * - converts BTF images to PNG
 * v3 r2 2020-02-22 by bnnm
 * - fixed png transparency
 * v3 r3 2020-02-26 by bnnm
 * - fixed encryption 1 (used in some of the Japanese version files)
 * - tweaked fseek/ftell
 * 
 * TODO: missing key for *.gif and *.jpg downloaded files, big cleanup, missing names
 */


#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <stdlib.h>
#include <sys/stat.h>

/* miniz (zlib replacement) from: https://github.com/richgel999/miniz */
#include "miniz.h" //#include "zlib.h"

/* ChaCha8 (decryption) from: https://cr.yp.to/chacha.html#chacha-paper */
#include "ecrypt-sync.h"

/* lodepng (png encoder): from https://github.com/lvandeve/lodepng */
#include "lodepng.h" 

/* make sure bigfiles work, not sure which is better in all PCs */
//#define khux_ftello ftello       //GCC
//#define khux_fseeko fseeko       //GCC
#define khux_ftello ftello64     //GCC
#define khux_fseeko fseeko64     //GCC
//#define khux_ftello _ftelli64    //MSVC
//#define khux_fseeko _fseeki64    //MSVC

#define KHUX_PATH_LIMIT 32767
#define KHUX_MAX_FILES 10
/* game loads and decrypts whole BGADs in memory, so fixed sizes shouldn't be a problem 
 * (known max around 30MB, use 50MB just in case) */
#define BGAD_MAX_DATA_SIZE (50*1024*1024)
#define BGAD_MAX_NAME_SIZE 0x2000
#define BGAD_MAX_IMG_SIZE (25*1024*1024)
#define BGAD_MAX_FILES 0x400000

/* ************************************************************************* */

static inline void put_u16be(uint8_t* buf, uint16_t v) {
    buf[0] = (uint8_t)((v >> 8u) & 0xFF);
    buf[1] = (uint8_t)(v & 0xFF);
}
static inline void put_u16le(uint8_t* buf, uint16_t v) {
    buf[0] = (uint8_t)(v & 0xFF);
    buf[1] = (uint8_t)(v >> 8u);
}
static inline void put_u32be(uint8_t* buf, uint32_t v) {
    buf[0] = (uint8_t)((v >> 24u) & 0xFF);
    buf[1] = (uint8_t)((v >> 16u) & 0xFF);
    buf[2] = (uint8_t)((v >> 8u) & 0xFF);
    buf[3] = (uint8_t)(v & 0xFF);
}
static inline void put_u32le(uint8_t* buf, uint32_t v) {
    buf[0] = (uint8_t)(v & 0xFF);
    buf[1] = (uint8_t)((v >> 8u) & 0xFF);
    buf[2] = (uint8_t)((v >> 16u) & 0xFF);
    buf[3] = (uint8_t)((v >> 24u) & 0xFF);
}

static inline uint16_t get_u16be(uint8_t* p) {
    return (uint16_t)((p[0]<<8u) | (p[1]));
}
static inline uint32_t get_u32be(uint8_t* p) {
    return (uint32_t)((p[0] << 24u) | (p[1] << 16u) | (p[2] << 8u) | (p[3]));
}
static inline uint16_t get_u16le(uint8_t* p) {
    return (uint16_t)((p[0]) | (p[1] << 8u));
}
static inline uint32_t get_u32le(uint8_t* p) {
    return (uint32_t)((p[0]) | (p[1] << 8u) | (p[2] << 16u) | (p[3] << 24u));
}


/* ************************************************************************* */

static int starts_with(const char* str, const char* pre) {
    if (!str || !pre)
        return 0;
    
    int str_len = strlen(str);
    int pre_len = strlen(pre);
    if (pre_len > str_len)
        return 0;
    return strncmp(str, pre, pre_len) == 0;
}

static int ends_with(const char* str, const char* suf) {
    if (!str || !suf)
        return 0;
    
    int str_len = strlen(str);
    int suf_len = strlen(suf);
    if (suf_len > str_len)
        return 0;
    return strncmp(str + str_len - suf_len, suf, suf_len) == 0;
}

/* ************************************************************************* */

typedef struct {
    const char* path;
    FILE* files[KHUX_MAX_FILES];
    uint32_t sizes[KHUX_MAX_FILES];
    int current;
    int count;
    uint64_t offset;
    uint64_t size;
} khux_file_t;

/* big files are chunked in 2GBs, but data and offsets are continuous, 
 * so we need some ghetto stream reader */
static khux_file_t* kfopen(const char* path) {
    khux_file_t* kfile = malloc(sizeof(khux_file_t));
    if (!kfile) return NULL;
    
    kfile->files[0] = fopen(path, "rb");
    if (!kfile->files[0]) {
        free(kfile);
        return NULL;
    }
    kfile->count = 1;
    kfile->current = 0;
    
    kfile->path = path;
    kfile->offset = 0;
    kfile->size = 0;
    
    for (int i = 1; i < KHUX_MAX_FILES; i++) {
        char name[KHUX_PATH_LIMIT];

        sprintf(name, "%s.%i", path, i);
        kfile->files[i] = fopen(name, "rb");
        if (!kfile->files[i]) 
            break;
        kfile->count++;
    }

    for (int i = 0; i < kfile->count; i++) {
        khux_fseeko(kfile->files[i], 0, SEEK_END);
        kfile->sizes[i] += khux_ftello(kfile->files[i]);
        khux_fseeko(kfile->files[i], 0, SEEK_SET);
        kfile->size += kfile->sizes[i];
    }

    return kfile;
}
static void kfclose(khux_file_t* kfile) {
    if (!kfile) return;

    for (int i = 0; i < kfile->count; i++) {
        fclose(kfile->files[i]);
    }
    free(kfile);
}
static uint64_t kftell(khux_file_t* kfile) {
    return kfile->offset;
}
static int kfread(uint8_t* buf, int length, khux_file_t* kfile) {
    int total_bytes = 0;

    while (length > 0) {
        if (kfile->current >= kfile->count)
            break;

        size_t bytes = fread(buf, sizeof(uint8_t), length, kfile->files[kfile->current]);
        if (bytes != length) {
            kfile->current++;
        }

        kfile->offset += bytes;
        total_bytes += bytes;
        buf += bytes;
        length -= bytes;
    }

    return total_bytes;
}
static int kfskip(int length, khux_file_t* kfile) {
    int total_bytes = 0;

    while (length > 0) {
        if (kfile->current >= kfile->count)
            break;

        off_t cur1 = khux_ftello(kfile->files[kfile->current]);
        khux_fseeko(kfile->files[kfile->current], length, SEEK_CUR);
        off_t cur2 = khux_ftello(kfile->files[kfile->current]);
        if (cur2 > kfile->sizes[kfile->current])
            cur2 = kfile->sizes[kfile->current];

        size_t bytes = cur2 - cur1;
        if (bytes != length) {
            kfile->current++;
        }

        kfile->offset += bytes;
        total_bytes += bytes;
        length -= bytes;
    }

    return total_bytes;
}

/* ************************************************************************* */

static void xor8b_decrypt(uint8_t* buf, int length, int key) {

    for (int i = 0; i < length; i++) {
        key = 0x19660D * key + 0x3C6EF35F;
        buf[i] ^= key;
    }
}

static void xor32b_decrypt(uint8_t* buf, int length, int key) {
    int* buf32 = (int*)buf;
    int int_count = (length + 3) >> 2;

    /* key update seems to be a common PRNG from "Numerical Recipes in C" */
    for (int i = 0; i < int_count; i++) {
        key = 0x19660D * key + 0x3C6EF35F;
        buf32[i] ^= key;

        //TODO: this fails for some signedness stuff? not sure
        //xor = get_u32le(&buf[i*4]) ^ key;
        //put_u32le(&buf[i*4], xor);
    }
}

static void chacha8_decrypt(uint8_t* buf, int buf_size, const uint8_t* key, const uint8_t* iv_base, const uint8_t* iv_file) {
    uint8_t iv[8];

    /* final IV is a base IV mixed with the last 8 bytes of a file (may be shared) */
    for (int i = 0; i < 8; i++) {
        iv[i] = iv_base[i] ^ iv_file[i];
    }

    /* fixed sizes, and the game calls again setup per file */
    uint32_t ivsize = 8*8;
    uint32_t keysize = 32*8;
    ECRYPT_ctx ctx = {0};

    ECRYPT_init();    
    ECRYPT_keysetup(&ctx, key, keysize, ivsize);
    ECRYPT_ivsetup(&ctx, iv);
    ECRYPT_decrypt_bytes(&ctx, buf, buf, buf_size); /* src/dst can be the same*/
}

/* ************************************************************************* */

typedef struct {
    const char* in_path;
    const char* out_path;
    char out_temp[KHUX_PATH_LIMIT];
    int out_len;

    int list_only;
    int print_names;
    int disable_img;
    int enable_bmp;
    int key_type;
    int write_from;
    int write_max;
    const char* prefix;
    const char* suffix;
    int dump_small;
} khux_config_t;

typedef struct {
    uint32_t id;
    uint16_t version;
    uint16_t iv_type;
    uint16_t header_size;
    uint16_t name_size;
    uint16_t encryption;
    uint16_t compression;
    uint32_t data_size;
    uint32_t uzdata_size;
} bgad_header_t;

typedef struct {
    uint32_t id;
    uint32_t version;
    uint32_t encryption;
} bgi_header_t;

typedef struct bgad_info_t bgad_info_t;

typedef struct {
    int count1;
    int count2;
    uint64_t t1[BGAD_MAX_FILES];
    uint32_t t2[BGAD_MAX_FILES];
    uint32_t t3[BGAD_MAX_FILES];
    uint8_t* t4;
    
    int last_t1i;
    int last_t3i;
    char last_name[BGAD_MAX_NAME_SIZE];
} index_info_t;

struct bgad_info_t {
    bgad_header_t bgad;
    bgi_header_t bgi;
    char name[BGAD_MAX_NAME_SIZE];
    uint8_t data[BGAD_MAX_DATA_SIZE];
    uint8_t uzdata[BGAD_MAX_DATA_SIZE];
    uint8_t imgdata[BGAD_MAX_IMG_SIZE];    

    uint64_t offset;
    const uint8_t* key_file;
    uint8_t iv_file[8];
    uint8_t* buf;   // points to data chunk
    int buf_size;   // size of data chunk
    
    char name_origin; //xored/index/unknown

    int count;
    int written;
    
    int is_index;
    bgad_info_t* index_file;
    index_info_t* index_info;
    
    khux_config_t* cfg;
    
    int is_small;
};


// TODO: not cleaned up, not portable, too much alloc, whatevs
int decode_btf(uint8_t *src_arg, int src_size, int *p_x1, int *p_y1, uint8_t **p_dstbuf, int *p_dstbuf_len, uint8_t *p_outflag1, uint8_t *p_outflag2, int flag_half, int *p_x2, int *p_y2) {
    const static uint8_t btf_id[] = {
        0x89,0x42,0x54,0x46,0,0
    };

    unsigned int v11; // r8
    uint8_t *imgbuf; // r9
    int flags2; // r10
    unsigned int img_x2; // r11
    int tmp_multi; // lr
    uint8_t *src; // r4
    int p_y1tmp1; // r5
    int p_x1tmp1; // r6
    unsigned int result; // r0
    int img_y1; // r9
    int img_x1; // r5
    unsigned int *datbuf_len_p; // r6
    unsigned int datbuf_len; // r4
    uint8_t *datbuf; // r8
    unsigned int imgbuf_tmplen; // r0
    unsigned int p_x1tmp1_; // r2
    int v27; // r3
    int v28; // r1
    int v29; // r0
    uint8_t *v30; // r1
    unsigned int v31; // r3
    int v32; // r2
    uint8_t *v33; // r5
    uint8_t *v34; // r4
    int v35; // r3
    int v36; // t1
    uint8_t *imgptr; // r6
    int dstpos; // r1
    int ctr1; // r8
    uint8_t *dstptr; // r1
    int ctr3; // r3
    int ctr1b; // r4
    uint8_t ctr1_test; // zf
    unsigned int val; // r5
    unsigned int val_shr4; // r2
    int ctr2; // r3
    char outflag2_test; // r0
    uint8_t *dstptr_; // r4
    unsigned int v49; // r0
    int v50; // r3
    int v51; // r0
    uint8_t *v52; // r5
    uint8_t *v53; // r2
    int v54; // r1
    int v55; // t1
    unsigned int v56; // r12
    unsigned int v57; // r3
    int v58; // r5
    int v59; // r4
    unsigned int v60; // r3
    unsigned int v61; // r6
    int v62; // r8
    uint8_t *v63; // r5
    unsigned int v64; // r6
    int v65; // r3
    int v66; // r4
    int v67; // r12
    int v68; // r8
    unsigned int v69; // lr
    uint8_t *v70; // r8
    uint8_t *v71; // r4
    uint8_t *v72; // r2
    int v73; // t1
    unsigned int v74; // r4
    uint8_t *v75; // r2
    int v76; // t1
    int v77; // r6
    uint8_t *imgptr_; // r8
    int v79; // r2
    int v80; // r12
    int v81; // r5
    int v82; // r8
    unsigned int v83; // r0
    int *v84; // r6
    uint8_t *v85; // r3
    int *v86; // r1
    int v87; // t1
    uint8_t *v88; // r3
    unsigned int v89; // r0
    int v90; // t1
    int v91; // [sp+4h] [bp-5Ch]
    int v92; // [sp+Ch] [bp-54h]
    unsigned int v93; // [sp+10h] [bp-50h]
    int v94; // [sp+10h] [bp-50h]
    int dstbuf_len; // [sp+14h] [bp-4Ch]
    int img_y0; // [sp+18h] [bp-48h]
    int tmp_x1; // [sp+1Ch] [bp-44h]
    int tmp_y1; // [sp+20h] [bp-40h]
    __int16 flags1; // [sp+24h] [bp-3Ch]
    int *p_x1tmp2; // [sp+28h] [bp-38h]
    int *p_y1tmp2; // [sp+2Ch] [bp-34h]
    int v102; // [sp+30h] [bp-30h]
    unsigned int img_y3; // [sp+34h] [bp-2Ch]
    unsigned int img_y3a; // [sp+34h] [bp-2Ch]
    int img_y3b; // [sp+34h] [bp-2Ch]
    uint8_t *dstbuf; // [sp+38h] [bp-28h]
    int flags2_val; // [sp+3Ch] [bp-24h]
    unsigned int img_x3; // [sp+40h] [bp-20h]
    unsigned int img_x3a; // [sp+40h] [bp-20h]
    unsigned int img_x3b; // [sp+40h] [bp-20h]
    int img_x0; // [sp+44h] [bp-1Ch]
    int img_y2; // [sp+48h] [bp-18h]
    long unsigned int imgbuf_len; // [sp+4Ch] [bp-14h]
    unsigned int stack_guard = 0xDEADBEEF; // [sp+50h] [bp-10h]

    src = src_arg;
    p_y1tmp1 = (int)p_y1;
    p_x1tmp1 = (int)p_x1;
    if ( src_size >= 4 && !memcmp(btf_id, src_arg, 6u) )
    {
        p_x1tmp2 = (int *)p_x1tmp1;
        p_y1tmp2 = (int *)p_y1tmp1;
        (flags2) = *((int16_t *)src + 8);
        img_x2 = *((unsigned __int16 *)src + 15);
        img_y1 = *((unsigned __int16 *)src + 12);
        img_x1 = *((unsigned __int16 *)src + 11);
        img_y2 = *((unsigned __int16 *)src + 16);
        flags1 = *((int16_t *)src + 3);
        if ( flags2 & 1 )
        {
            datbuf_len_p = (unsigned int *)(src + 36);
            img_y3 = *((unsigned __int16 *)src + 14);
            img_x3 = *((unsigned __int16 *)src + 13);
            flags2_val = *((unsigned __int16 *)src + 17);
        }
        else
        {
            img_y3 = *((unsigned __int16 *)src + 14);
            img_x3 = *((unsigned __int16 *)src + 13);
            datbuf_len_p = (unsigned int *)(src + 34);
            flags2_val = 0;
        }

        datbuf_len = *datbuf_len_p;
        datbuf = malloc(*datbuf_len_p);
        memcpy(datbuf, datbuf_len_p + 1, datbuf_len);

        if ( flag_half )
        {
            img_y0 = (unsigned int)(img_y1 + 1) >> 1;
            img_x0 = (unsigned int)(img_x1 + 1) >> 1;
        }
        else
        {
            img_y0 = img_y1;
            img_x0 = img_x1;
        }

        dstbuf_len = 4 * img_x1 * img_y1;
        dstbuf = malloc(4 * img_x1 * img_y1);
        memset(dstbuf, 0, 4 * img_x1 * img_y1);

        if ( flags2 & 8 )
        {
            if ( flags2_val )
            {
                tmp_x1 = img_x1;
                tmp_y1 = img_y1;
                imgbuf_tmplen = img_y2 * img_x2 + 4 * flags2_val;
            }
            else
            {
                tmp_x1 = img_x1;
                tmp_y1 = img_y1;
                imgbuf_tmplen = 4 * img_x2 * img_y2;
            }
            imgbuf_len = imgbuf_tmplen;
            imgbuf = malloc(imgbuf_tmplen);
            uncompress(imgbuf, &imgbuf_len, datbuf, datbuf_len);
            free(datbuf);
        }
        else
        {
            tmp_x1 = img_x1;
            tmp_y1 = img_y1;
            imgbuf = datbuf;
            imgbuf_len = datbuf_len;
        }

        p_y1tmp1 = img_x3;
        p_x1tmp1_ = img_y3;

        v11 = img_x3 >> flag_half;
        tmp_multi = flag_half;
        result = img_y3 >> flag_half;
        if ( flags2 & 0x10 )
        {
            if ( img_y2 )
            {
                tmp_multi = img_x2 & 1;
                flags2 = 0;
                imgptr = &imgbuf[4 * flags2_val];
                dstpos = img_x0 * (unsigned __int16)result + (unsigned __int16)v11;
                ctr1 = 1;
                dstptr = &dstbuf[4 * dstpos];
                do
                {
                    if ( img_x2 )
                    {
                        ctr3 = 0;
                        ctr1b = ctr1;
                        do
                        {
                            ctr1_test = (ctr1b & 1) == 0;
                            val = *imgptr;
                            ctr1b ^= 1u;
                            val_shr4 = val >> 4;
                            if ( !ctr1_test )
                                val_shr4 = val & 0xF;
                            *(int32_t *)&dstptr[4 * ctr3] = *(int32_t *)&imgbuf[4 * val_shr4];
                            if ( ctr1_test )
                                ++imgptr;
                            ++ctr3;
                        }
                        while ( img_x2 != ctr3 );
                        ctr2 = img_x2 & 1;
                        if ( img_x2 & 1 )
                            ctr2 = 1;
                        ctr1 ^= ctr2;
                    }
                    dstptr += 4 * img_x0;
                    ++flags2;
                }
                while ( flags2 != img_y2 );
            }
        }
        else
        {
            if ( !flags2_val )
                goto LABEL_45;
            v27 = (unsigned __int16)result;
            v28 = img_x0 * (unsigned __int16)result;
            v29 = (int)&imgbuf[4 * flags2_val];
            v30 = &dstbuf[4 * (v28 + (unsigned __int16)v11)];
            if ( flags2 & 0x400 )
            {
                v56 = (unsigned int)(img_y2 + 1) >> 1;
                v57 = (img_x2 + 1) >> 1;
                if ( flag_half == 1 )
                {
                    if ( v56 )
                    {
                        v58 = 0;
                        do
                        {
                            if ( v57 )
                            {
                                v59 = 0;
                                do
                                {
                                    *(int32_t *)&v30[4 * v59] = *(int32_t *)&imgbuf[4 * *(uint8_t *)(v29 + v59)];
                                    ++v59;
                                }
                                while ( v57 != v59 );
                            }
                            ++v58;
                            v30 += 4 * img_x0;
                            v29 += v57;
                        }
                        while ( v58 != v56 );
                    }
                }
                else if ( v57 && v56 )
                {
                    flags2 = v29 + (img_x2 >> 1);
                    img_x3a = (unsigned int)&v30[8 * (img_x2 >> 1)];
                    v67 = 0;
                    v93 = img_x2 >> 1;
                    v68 = (int)&v30[4 * (img_x0 + 2 * (img_x2 >> 1))];
                    v91 = 8 * img_x0;
                    v92 = img_x2 & 1;
                    do
                    {
                        img_x2 = v29 + v67 * v57;
                        v69 = v93;
                        img_y3a = v68;
                        v102 = 2 * v67;
                        v70 = (uint8_t *)(v29 + v67 * v57);
                        v71 = (uint8_t *)(v29 + v67 * v57);
                        v72 = &v30[4 * img_x0 * 2 * v67];
                        if ( v93 )
                        {
                            do
                            {
                                v73 = *v71++;
                                --v69;
                                *(int32_t *)v72 = *(int32_t *)&imgbuf[4 * v73];
                                *((int32_t *)v72 + 1) = *(int32_t *)&imgbuf[4 * v73];
                                v72 += 8;
                            }
                            while ( v69 );
                            v72 = (uint8_t *)img_x3a;
                            v70 = (uint8_t *)flags2;
                        }
                        tmp_multi = (unsigned int)(img_y2 + 1) >> 1;
                        if ( v92 )
                            *(int32_t *)v72 = *(int32_t *)&imgbuf[4 * *v70];
                        if ( (v102 | 1) < img_y2 )
                        {
                            v74 = v93;
                            v75 = &v30[4 * (v102 | 1) * img_x0];
                            if ( v93 )
                            {
                                do
                                {
                                    v76 = *(uint8_t *)img_x2++;
                                    --v74;
                                    v77 = *(int32_t *)&imgbuf[4 * v76];
                                    *(int32_t *)v75 = *(int32_t *)&imgbuf[4 * v76];
                                    *((int32_t *)v75 + 1) = v77;
                                    v75 += 8;
                                }
                                while ( v74 );
                                v75 = (uint8_t *)img_y3a;
                                img_x2 = flags2;
                            }
                            if ( v92 )
                                *(int32_t *)v75 = *(int32_t *)&imgbuf[4 * *(uint8_t *)img_x2];
                        }
                        ++v67;
                        flags2 += v57;
                        v68 = img_y3a + v91;
                        img_x3a += v91;
                    }
                    while ( v67 != (unsigned int)(img_y2 + 1) >> 1 );
                }
            }
            else if ( flag_half )
            {
                v31 = ((img_y2 + img_y3) >> 1) - v27;
                if ( (int16_t)v31 )
                {
                    flags2 = (unsigned __int16)v31;
                    tmp_multi = (unsigned __int16)(((img_x3 + img_x2) >> 1) - v11);
                    v32 = 0;
                    do
                    {
                        if ( (unsigned __int16)((img_x3 + img_x2) >> 1) != (int16_t)v11 )
                        {
                            v33 = (uint8_t *)(v29 + v32 * (unsigned __int16)(2 * img_x2));
                            v34 = &v30[4 * img_x0 * v32];
                            v35 = (unsigned __int16)(((img_x3 + img_x2) >> 1) - v11);
                            do
                            {
                                v36 = *v33;
                                v33 += 2;
                                --v35;
                                *(int32_t *)v34 = *(int32_t *)&imgbuf[4 * v36];
                                v34 += 4;
                            }
                            while ( v35 );
                        }
                        ++v32;
                    }
                    while ( v32 != flags2 );
                }
            }
            else if ( img_y2 )
            {
                v65 = 0;
                do
                {
                    if ( img_x2 )
                    {
                        v66 = 0;
                        do
                        {
                            *(int32_t *)&v30[4 * v66] = *(int32_t *)&imgbuf[4 * *(uint8_t *)(v29 + v66)];
                            ++v66;
                        }
                        while ( img_x2 != v66 );
                    }
                    v30 += 4 * img_x0;
                    v29 += img_x2;
                    ++v65;
                }
                while ( v65 != img_y2 );
            }
        }
        goto LABEL_40;
    }
    for ( result = 0; ; result = 1 )
    {
        p_x1tmp1_ = stack_guard;
        if ( /*_stack_chk_guard ==*/ stack_guard == 0xDEADBEEF ) /* ??? */
            break;
LABEL_45:
        result = (unsigned __int16)result;
        dstptr_ = &dstbuf[4 * ((unsigned __int16)result * img_x0 + (unsigned __int16)v11)];
        if ( flags2 & 0x400 )
        {
            v60 = (unsigned int)(img_y2 + 1) >> 1;
            v61 = (img_x2 + 1) >> 1;
            if ( tmp_multi == 1 )
            {
                if ( v60 )
                {
                    img_x2 = (2 * img_x2 + 2) & 0x3FFFC;
                    v62 = 4 * v61;
                    v63 = imgbuf;
                    flags2 = 4 * img_x0;
                    do
                    {
                        v64 = v60;
                        memcpy(dstptr_, v63, v62);
                        v63 += img_x2;
                        dstptr_ += flags2;
                        v60 = v64 - 1;
                    }
                    while ( v64 != 1 );
                }
            }
            else if ( v61 && v60 )
            {
                img_x3b = img_x2 >> 1;
                v79 = (int)&imgbuf[4 * (img_x2 >> 1)];
                v80 = (int)&dstptr_[8 * (img_x2 >> 1)];
                v81 = 0;
                flags2 = (int)&dstptr_[4 * (img_x0 + 2 * (img_x2 >> 1))];
                v94 = 8 * img_x0;
                img_y3b = img_x2 & 1;
                do
                {
                    v82 = 2 * v81;
                    img_x2 = v61;
                    tmp_multi = (int)&imgbuf[4 * v81 * v61];
                    v83 = img_x3b;
                    v84 = (int *)tmp_multi;
                    v85 = &dstptr_[4 * 2 * v81 * img_x0];
                    v86 = (int *)tmp_multi;
                    if ( img_x3b )
                    {
                        do
                        {
                            v87 = *v86;
                            ++v86;
                            --v83;
                            *(int32_t *)v85 = v87;
                            *((int32_t *)v85 + 1) = v87;
                            v85 += 8;
                        }
                        while ( v83 );
                        v85 = (uint8_t *)v80;
                        v84 = (int *)v79;
                    }
                    if ( img_y3b )
                        *(int32_t *)v85 = *v84;
                    v61 = img_x2;
                    if ( (v82 | 1) < img_y2 )
                    {
                        v88 = &dstptr_[4 * (v82 | 1) * img_x0];
                        v89 = img_x3b;
                        if ( img_x3b )
                        {
                            do
                            {
                                v90 = *(int32_t *)tmp_multi;
                                tmp_multi += 4;
                                --v89;
                                *(int32_t *)v88 = v90;
                                *((int32_t *)v88 + 1) = v90;
                                v88 += 8;
                            }
                            while ( v89 );
                            v88 = (uint8_t *)flags2;
                            tmp_multi = v79;
                        }
                        if ( img_y3b )
                            *(int32_t *)v88 = *(int32_t *)tmp_multi;
                    }
                    v79 += 4 * img_x2;
                    ++v81;
                    flags2 += v94;
                    v80 += v94;
                }
                while ( v81 != (unsigned int)(img_y2 + 1) >> 1 );
            }
        }
        else if ( tmp_multi )
        {
            v49 = ((img_y2 + p_x1tmp1_) >> 1) - result;
            if ( (int16_t)v49 )
            {
                flags2 = ((img_x2 + p_y1tmp1) >> 1) - (unsigned __int16)v11;
                v50 = (unsigned __int16)v49;
                tmp_multi = (unsigned __int16)(((img_x2 + p_y1tmp1) >> 1) - v11);
                v51 = 0;
                do
                {
                    if ( (int16_t)flags2 )
                    {
                        v52 = &imgbuf[4 * v51 * (unsigned __int16)(2 * img_x2)];
                        v53 = &dstptr_[4 * img_x0 * v51];
                        v54 = tmp_multi;
                        do
                        {
                            v55 = *(int32_t *)v52;
                            v52 += 8;
                            --v54;
                            *(int32_t *)v53 = v55;
                            v53 += 4;
                        }
                        while ( v54 );
                    }
                    ++v51;
                }
                while ( v51 != v50 );
            }
        }
        else if ( img_y2 )
        {
            imgptr_ = imgbuf;
            do
            {
                memcpy(dstptr_, imgptr_, 4 * img_x2);
                imgptr_ += 4 * img_x2;
                dstptr_ += 4 * img_x0;
                --img_y2;
            }
            while ( img_y2 );
        }
LABEL_40:
        //(v11) = (int16_t)p_y2;
        p_y1tmp1 = (int)p_x2;
        free(imgbuf);
        *p_x1tmp2 = tmp_x1;
        *p_y1tmp2 = tmp_y1;
        *p_dstbuf = dstbuf;
        *p_dstbuf_len = dstbuf_len;
        *p_outflag1 = flags1 & 1;
        outflag2_test = 0;
        if ( flags2_val == 1 && *(int32_t *)dstbuf < 0x1000000u )
            outflag2_test = 1;
        *p_outflag2 = outflag2_test;
        *p_x2 = img_x0;
        *p_y2 = img_y0;
    }
    return result;
}

static int make_bmp(uint8_t* bmpbuf, int bmpbuf_len, int x, int y, uint8_t* imgbuf, int imgbuf_len) {

    if (imgbuf_len + 0x36 > bmpbuf_len) {
        printf("bmp too big: size %x vs max %x\n", imgbuf_len, bmpbuf_len);
        return 0;
    }

    int pos = 0;
    bmpbuf[pos++] = 0x42;
    bmpbuf[pos++] = 0x4d;
    for (int i = 0; i < 8; i++)
        bmpbuf[pos++] = 0x00;
    put_u32le(bmpbuf + 2, imgbuf_len + 0x36);

    bmpbuf[pos++] = 0x36;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x28;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x00;

    bmpbuf[pos++] = (x >> 0) & 0xFF;
    bmpbuf[pos++] = (x >> 8) & 0xFF;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = (y >> 0) & 0xFF;
    bmpbuf[pos++] = (y >> 8) & 0xFF;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x00;

    bmpbuf[pos++] = 0x01;
    bmpbuf[pos++] = 0x00;
    bmpbuf[pos++] = 0x20;
    for (int i = 0; i < 0x19; i++)
        bmpbuf[pos++] = 0x00;

    /* BMP expects BGRA with pre-multiplied alpha, lossless but it's a lot bigger */
    for (int i = 0; i < imgbuf_len; i += 4) {
        uint8_t r = imgbuf[i+0];
        uint8_t g = imgbuf[i+1];
        uint8_t b = imgbuf[i+2];
        imgbuf[i+0] = b;
        imgbuf[i+1] = g;
        imgbuf[i+2] = r;
    }

    //todo incorrect alpha settings in header
    //todo must reorder data
    
    memcpy(&bmpbuf[pos], imgbuf, imgbuf_len);

    return 0x36 + imgbuf_len;
}

static int make_png(uint8_t *pngbuf, int pngbuf_len, int x, int y, uint8_t* imgbuf, int imgbuf_len) {

    unsigned char* tmpbuf = NULL;
    size_t tmpbuf_len;

    /* PNG expects RBGA without pre-multiplied alpha, not lossless but not very noticeable */
    for (int i = 0; i < imgbuf_len; i += 4) {
        if (imgbuf[i+3] > 0) {
            imgbuf[i+0] = (float)imgbuf[i+0] / ((float)imgbuf[i+3] / 255.0f);
            imgbuf[i+1] = (float)imgbuf[i+1] / ((float)imgbuf[i+3] / 255.0f);
            imgbuf[i+2] = (float)imgbuf[i+2] / ((float)imgbuf[i+3] / 255.0f);
        }
    }

    unsigned error = lodepng_encode32(&tmpbuf, &tmpbuf_len, imgbuf, x, y);
    if (error) {
        printf("png conversion error %u: %s\n", error, lodepng_error_text(error));
        goto fail;
    }

    if (tmpbuf_len > pngbuf_len) {
        printf("png too big: size %x vs max %x\n", tmpbuf_len, pngbuf_len);
        goto fail;
    }

    memcpy(pngbuf, tmpbuf, tmpbuf_len);
    free(tmpbuf);

    return tmpbuf_len;
fail:
    free(tmpbuf);
    return 0;
}

/* BTF seems like a custom PNG (flags that indicate format and usually zlibbed image)
 * we just decode to RGBA using the original function and reencode to other image */
static void parse_btf(bgad_info_t* info) {
    if (info->buf_size < 0x04) {
        if (ends_with(info->name, "png")) {
            printf("small png over size in file %i at %"PRIx64"\n", info->count, info->offset);
        }
        return;
    }
    if (info->cfg->disable_img)
        return;

    /* check values  */
    if (get_u32be(info->buf + 0x00) != 0x89425446) { /* "\89BTF" */
        return;
    }

    uint8_t* imgbuf = NULL;
    int imgbuf_len;
    uint8_t flag1 = 0, flag2 = 0;
    int x1 = 0, y1 = 0, x2 = 0, y2 = 0;

    decode_btf(info->buf, info->buf_size, &x1, &y1, &imgbuf, &imgbuf_len, &flag1, &flag2, 0, &x2, &y2);

    /* not seen */
    if (x1 != x2 || y1 != y2) {
        printf("BTF diff size: x1=%i, y1=%i, x2=%i, y2=%i in file %i at %"PRIx64"\n", x1,y1,x2,y2, info->count, info->offset);
    }
    /* flag2 seems to be used when file is null? (black box) */
    if (flag1 != 1 || (flag2 != 0 && flag2 != 1)) {
        printf("BTF diff flag: flag1=%i, flag2=%i in file %i at %"PRIx64"\n", flag1, flag2, info->count, info->offset);
    }

    if (info->cfg->enable_bmp) {
        int bmpbuf_len = make_bmp(info->imgdata, BGAD_MAX_IMG_SIZE, x1, y2, imgbuf, imgbuf_len);
        if (bmpbuf_len <= 0) goto fail;

        info->buf = info->imgdata;
        info->buf_size = bmpbuf_len;
    }
    else {
        int pngbuf_len = make_png(info->imgdata, BGAD_MAX_IMG_SIZE, x1, y2, imgbuf, imgbuf_len);
        if (pngbuf_len <= 0) goto fail;

        info->buf = info->imgdata;
        info->buf_size = pngbuf_len;
    }

    free(imgbuf);
    return;
    
fail:
    free(imgbuf);
    printf("can't convert BTF in file %i at %"PRIx64"\n", info->count, info->offset);
}

static void parse_bgi(bgad_info_t* info) {
    if (info->buf_size < 0x10)
        return;

    info->bgi.id             = get_u32be(info->buf + 0x00);
    info->bgi.encryption     = get_u32le(info->buf + 0x04);
    info->bgi.version        = get_u32le(info->buf + 0x08); /* or encryption_flag */

    if (info->bgi.id != 0x89424749) { /* "\89BGI" */
        return;
    }

    switch(info->bgi.version) {
        case 0: /* not encrypted */
            return;
        case 1: /* encrypted */
            break;
        default:
            printf("unknown BGI version\n");
            return;
    }

    switch(info->bgi.encryption) {

        case 3: { /* chacha8 */
            const static uint8_t iv_bgi[8] = {
               0xEA,0x74,0x35,0x0A, 0x0F,0x34,0xDB,0xC4,
            };

            info->buf_size = info->buf_size - 0x08;

            const uint8_t *iv = info->buf + info->buf_size;
            for (int i = 0; i < 8; i++) {
                info->iv_file[i] = iv[i];
            }

            chacha8_decrypt(info->buf + 0x0c, info->buf_size - 0x0c, info->key_file, iv_bgi, info->iv_file);
            break;
        }

        default:
            printf("unknown BGI encryption type\n");
            return;
    }
    
    /* set not encrypted */
    put_u32le(info->buf + 0x08, 0);
}

static void get_index_name(char* name, bgad_info_t* info) {

    if (info->is_index) {
        if      (info->bgad.name_size == 1)
            strcpy(name, "/");
        else if (info->bgad.name_size == 3)
            strcpy(name, "md5");
        else if (info->bgad.name_size == 4)
            strcpy(name, "size");
        else
            name[0] = '\0';
        return;
    }
    
    if (info->index_file == NULL || info->index_info == NULL)
        goto fail;

    int pos1 = -1;
    for (int i = info->index_info->last_t1i; i < info->index_info->count1; i++) {
        if (info->index_info->t1[i] == info->offset) {
            pos1 = i;
            info->index_info->last_t1i = i; /* optimz, offsets are ordered */
        }
        else if (info->index_info->t1[i] > info->offset) {
            break;
        }
    }
    if (pos1 < 0)
        goto test2;

    int pos2 = -1;
    if (info->index_info->t2[pos1] != 0) {
        pos2 = info->index_info->t2[pos1];
    }
/*
    int pos2 = -1;
    for (int i = 0; i < info->index_info->count2; i++) {
        if (info->index_info->t2[i] != pos1)
            continue;

        pos2 = i;
        break;
    }
*/
    if (pos2 < 0)
        goto test2;
    
    char* namebuf = (char*)info->index_info->t4 + info->index_info->t3[pos2];
    strcpy(name, namebuf);
    info->index_info->last_t3i = pos2;
    info->name_origin = 'i';
    return;

test2: {
    /* often some names aren't pointed at, but previous name is, so we can find 
     * prev name and use next, if size matches */
    int start = info->index_info->last_t3i;
    int max = info->index_info->last_t3i + 30;
    if (max > info->index_info->count2)
        max = info->index_info->count2;

    int pos3 = -1;
    for (int i = start; i < max - 1; i++) {
        char* namebuf = (char*)info->index_info->t4 + info->index_info->t3[i];
        if (strcmp(info->index_info->last_name, namebuf) == 0) {
            pos3 = i;
            break;
        }
    }
    if (pos3 < 0)
        goto test3;

    char *namenext = (char*)info->index_info->t4 + info->index_info->t3[pos3+1];
    if (strlen(namenext) != info->bgad.name_size) {
        goto test3;
    }

    strcpy(name, namenext);
    info->index_info->last_t3i = pos3;
    info->name_origin = 'I';
    return;
}
test3:
    /* early files have 1:1 index<>name but aren't referenced anymore,
     * we can assume order is still fine */
    if (info->count > info->index_info->count2)  
        goto fail;

    char* namebuf2 = (char*)info->index_info->t4 + info->index_info->t3[info->count];
    strcpy(name, namebuf2);

    if (strlen(name) != info->bgad.name_size) {
        goto fail;
    }

    info->name_origin = '1';
    return;
    
fail:
    name[0] = '\0';
}

static int is_name_ok(char* name, int len) {
    if (len == 0)
        return 0;
    /* most later files have a different algo/key for the name */
    for (int i = 0; i < len; i++) {
        if (name[i] < 0x20 || name[i] > 0x7f) {
            return 0;
        }
    }
    return 1;
}

static void get_name(khux_file_t* kfile, bgad_info_t* info) {
    char name[BGAD_MAX_NAME_SIZE];
    int name_ok;


    memcpy(name, info->name, info->bgad.name_size);
#if 0 //not ok
    switch(info->bgad.encryption) {
        case 1:
            xor8b_decrypt((uint8_t*)name, info->bgad.name_size, info->bgad.data_size);
            break;

        default:
            xor32b_decrypt((uint8_t*)name, info->bgad.name_size, info->bgad.data_size);
            break;
    }
#endif
    xor32b_decrypt((uint8_t*)name, info->bgad.name_size, info->bgad.data_size);
    name[info->bgad.name_size] = '\0';
    info->name_origin = 'x';

    name_ok = is_name_ok(name, info->bgad.name_size);
    if (!name_ok) {
        get_index_name(name, info);
    }

    if (name[0] == '\0') {
        const char* base = strrchr(kfile->path, '/');
        if (!base)
            base = strrchr(kfile->path, '\\');

        if (!base)
            base = kfile->path;
        else
            base += 1;
        sprintf(name, "%s__%08i.dat", base, info->count + 1);    
        
        info->name_origin = 'u';
    }

    if (strcmp(name, "/") == 0) { /* invalid filename on all OSes */
        strcpy(name,".index");
    }


    /* in case of bad name decryption windows may not like */
    for (int i = 0; i < BGAD_MAX_NAME_SIZE; i++) {
        char val = name[i];
        if (val == '\0')
            break;
        if (val == ':' || val == '*' || val == '"' || val == '?' || val == '<' || val == '>' || val == '|')
            name[i] = '#';
    }
    
    strcpy(info->name, name);
    if (info->index_info != NULL) {
        strcpy(info->index_info->last_name, name);
    }
    
}

static int read_bgad(khux_file_t* kfile, bgad_info_t* info) {
    info->offset = kftell(kfile); /* before reads */


    uint8_t buf[0x18];
    int bytes = kfread(buf, sizeof(buf), kfile);
    if (bytes != sizeof(buf)) {
        if (bytes > 0)
            printf("can't read BGAD (missing 0x%x)\n", bytes);
        return 0;
    }

    info->bgad.id             = get_u32be(buf + 0x00);
    info->bgad.version        = get_u16le(buf + 0x04);
    info->bgad.iv_type        = get_u16le(buf + 0x06);
    info->bgad.header_size    = get_u16le(buf + 0x08);
    info->bgad.name_size      = get_u16le(buf + 0x0a);
    info->bgad.encryption     = get_u16le(buf + 0x0c);
    info->bgad.compression    = get_u16le(buf + 0x0e);
    info->bgad.data_size      = get_u32le(buf + 0x10);
    info->bgad.uzdata_size    = get_u32le(buf + 0x14);
    
    info->is_small = info->bgad.uzdata_size <= 0x04;
    

    if (info->bgad.id != 0x42474144) { /* "BGAD" */
        printf("unknown BGAD id %08x\n", info->bgad.id);
        goto fail;
    }

    if (info->bgad.name_size + 4 > BGAD_MAX_NAME_SIZE
            || info->bgad.data_size > BGAD_MAX_DATA_SIZE 
            || info->bgad.uzdata_size > BGAD_MAX_DATA_SIZE) {
        /* name needs extra since it decrypts 32b at a time */
        printf("wrong BGAD sizes at %"PRIx64"\n", info->offset);
        goto fail;
    }

    if (info->bgad.version != 2) {
        /* all files use v2, even those from the 1.0 APK of the JP release */
        printf("unknown BGAD version\n");
        goto fail;
    }
    
    if (kfread((uint8_t*)info->name, info->bgad.name_size, kfile) != info->bgad.name_size) {
        printf("wrong BGAD name read\n");
        goto fail;
    }

    /* get name first to properly filter */
    get_name(kfile, info);

    if (!info->is_index) {
        int skip = 0;

        if (info->cfg->write_from && info->count < info->cfg->write_from)
            skip = 1;

        if (!info->cfg->dump_small && info->is_small)
            skip = 1;

        if ((info->cfg->prefix != NULL && !starts_with(info->name, info->cfg->prefix)) ||
            (info->cfg->suffix != NULL && !ends_with(info->name, info->cfg->suffix)) || 
            info->cfg->list_only)
            skip = 1;

        if (skip) {
            kfskip(info->bgad.data_size, kfile);   
            return 1;
        }
    }


    if (kfread(info->data, info->bgad.data_size, kfile) != info->bgad.data_size) {
        printf("wrong BGAD data read\n");
        goto fail;
    }

    info->buf = info->data;
    info->buf_size = info->bgad.data_size;

    switch(info->bgad.iv_type) {
        case 4: /* initialization vector for chacha8 at BGAD end */
            info->buf_size -= 0x08;

            const uint8_t *iv_ptr = info->buf + info->buf_size;
            for (int i = 0; i < 8; i++) {
                info->iv_file[i] = iv_ptr[i];
            }
            break;

        default:  /* none */
            /* shouldn't happen together with encryption 3 but just in case
             * value 2 exists for some files with encryption 2 (placeholders?) 
             * but game only checks value 4 */
            memset(info->iv_file,0, sizeof(info->iv_file));
            break;
    }

    switch(info->bgad.encryption) {
        case 1: /* used in few files in the JP release */
            xor8b_decrypt(info->buf, info->buf_size, info->bgad.name_size);
            break;

        case 2:
            xor32b_decrypt(info->buf, info->buf_size, info->bgad.name_size);
            break;

        case 3: {
            const static uint8_t iv_bgad[8] = {
               0x62,0xC0,0xD9,0x49, 0x9B,0x15,0x83,0x72,
            };
            chacha8_decrypt(info->buf, info->buf_size, info->key_file, iv_bgad, info->iv_file);
            break;
        }

        /* in code but not used by any files */
        case 0: /* no encryption */
        default:
            printf("unknown BGAD encryption type\n");
            goto fail;
    }

    switch(info->bgad.compression) {
        case 0:
            break;

        case 2: {
            long unsigned int size = info->bgad.uzdata_size;
            int zerror = uncompress(info->uzdata, &size, info->buf, info->buf_size);
            if (zerror != Z_OK) {
                printf("error decompressing BGAD data: %i\n", zerror);
                goto fail;
            }

            info->buf = info->uzdata;
            info->buf_size = size;
            break;
        }
        default:
            printf("unknown BGAD compression type\n");
            goto fail;
    }

    /* data may contain BGI, that can be decrypted further */
    parse_bgi(info);

    /* data may contain BTF, that can be converted further */
    parse_btf(info);


    /* fix unknown names a bit, now that we have data */
    if (info->name_origin == 'u') {
        uint32_t data_id = get_u32be(info->buf + 0x00);

        if (data_id == 0x89504E47) /* PNG */
            strcat(info->name, ".png");
        else if (data_id == 0x414B4220) /* AKB */
            strcat(info->name, ".akb");
        else if (data_id == 0x4C574600) /* LWF */    
            strcat(info->name, ".lwf");
        else if (data_id == 0x7B0D0A20) /* json start */
            strcat(info->name, ".json");
        else if (data_id == 0x7B0A2020) /* json start */
            strcat(info->name, ".ExportJson");
        else if (data_id == 0x4D415000) /* MAP */
            strcat(info->name, ".bin"); /* ??? */
        else if (data_id == 0x53544700) /* STG */
            strcat(info->name, ".bin");
        else if (data_id == 0xEFBBBF3C || data_id == 0x3C3F786D) /* XML start */
            strcat(info->name, ".plist");
    }

    return 1;
fail:
    printf("error in file %i at %"PRIx64"\n",  info->count, info->offset);
    return 0;
}

/* ************************************************************************* */

/* BGAD have encrypted names, XORed in early files but unknown in later ones
 * (maybe chacha8 with unknown key since name depends on IV). KHUX doesn't seem
 * to decrypt the name, but there is a companion .png index file with names.
 * Not all files have an unique entry/name in the index though, since sometimes
 * old files get replaced by inserting new ones at the end. */
static void read_index(khux_file_t* kfile, bgad_info_t* info) {

    if (ends_with(kfile->path, ".png")) {
        info->is_index = 1;
        return;
    }
    else if (!ends_with(kfile->path, ".mp4")) {
        return;
    }

    /* get companion ".png" */
    char name[KHUX_PATH_LIMIT];
    strcpy(name, kfile->path);
    strcpy(name + strlen(name) - 3, "png");

    khux_file_t* kindex = NULL;

    kindex = kfopen(name);
    if (!kindex) goto fail;

    info->index_file = calloc(1, sizeof(bgad_info_t));
    if (!info->index_file) goto fail;

    info->index_info = calloc(1, sizeof(index_info_t));
    if (!info->index_info) goto fail;

    info->index_file->is_index = 1;
    info->index_file->cfg = info->cfg;
    info->index_file->key_file = info->key_file;
    int bgad_ok = read_bgad(kindex, info->index_file);
    if (!bgad_ok) goto fail;

    
    /* header */
    uint8_t* bufptr = info->index_file->buf + 0x0c;
    info->index_info->count1 = get_u32le(bufptr + 0x00); /* offsets in table 1 */
    info->index_info->count2 = get_u32le(bufptr + 0x04); /* ids/names in table 2/3 */
    bufptr += 0x08;
    
    if (info->index_info->count1 > BGAD_MAX_FILES || 
        info->index_info->count2 > BGAD_MAX_FILES)
        goto fail;

    /* table1: 64b offsets to BGADs, but not to all */
    for (int i = 0; i < info->index_info->count1; i++) {
        info->index_info->t1[i] = 
            ((int64_t)get_u32le(bufptr + 0x00) << 0) |
            ((int64_t)get_u32le(bufptr + 0x04) << 32);
        bufptr += 0x08;
    }

    /* table2: offset positions (not ordered and some repeats) */
    for (int i = 0; i < info->index_info->count2; i++) {
        /* reverse lookup*/
        int offpos = get_u32le(bufptr + 0x00);
        /* repeats change names too */
        //if (info->index_info->t2 != 0)
        //    continue;
        info->index_info->t2[offpos] = i;
        
        bufptr += 0x04;
    }
    /*
    for (int i = 0; i < info->index_info->count2; i++) {
        info->index_info->t2[i] = get_u32le(bufptr + 0x00);
        bufptr += 0x04;
    }
    */

    /* table3: name table offsets (from t4) */
    for (int i = 0; i < info->index_info->count2; i++) {
        info->index_info->t3[i] = get_u32le(bufptr + 0x00);
        bufptr += 0x04;
    }
    
    /* table4: null-terminated names */
    info->index_info->t4 = bufptr;


    kfclose(kindex);
    return;
fail:
    kfclose(kindex);
    free(info->index_file);
    info->index_file = NULL;
    free(info->index_info);
    info->index_info = NULL;
    printf("WARNING: .png index not found, may not generate proper names\n");
    return;
}

static int set_key(khux_file_t* kfile, bgad_info_t* info, int key_type) {
    if (key_type == 0) {
        /* autodetect based on known patterns */
        if ((ends_with(kfile->path, "misc.mp4") && kfile->size < 0x10000000) ||
            (ends_with(kfile->path, "misc.png") && kfile->size < 0x00100000)) {
            key_type = 1;
        } 
        else if (ends_with(kfile->path, ".mp4") || ends_with(kfile->path, ".png")) {
            key_type = 2;
        }
        else if (ends_with(kfile->path, ".gif") || ends_with(kfile->path, ".jpg")) {
            key_type = 4;
        }

        //printf("detected key %i\n", key_type);
    }

    switch(key_type) {
        case 1: { /* small files in .apk */
            const static uint8_t key1[32] = {
                0x5C,0xA5,0x6C,0x58,0x27,0xFA,0x15,0xCF,0x1E,0xCE,0x2A,0x37,0x18,0x09,0x53,0xB8,
                0x01,0xDE,0xBF,0xD0,0xA7,0x1D,0xD6,0xAA,0x6D,0xD1,0xD4,0xF4,0x14,0xA5,0xFB,0xC4
            };
            info->key_file = key1;
            break;
        }

        case 2: { /* downloaded files inside "r" folder */
            const static uint8_t key2[32] = {
                0x3c,0x84,0x99,0xbf,0x7e,0xee,0x43,0xbd,0x1b,0x4d,0xde,0x85,0x37,0x25,0xa1,0x10,
                0xf0,0x91,0x4c,0x76,0xc1,0x67,0xbe,0x9d,0x3c,0x90,0x2c,0xbe,0xe7,0x90,0xb0,0x3e,
            };
            info->key_file = key2;
            break;
        }

        case 3: { /* encrypted/saved files? */
            const static uint8_t key3[32] = {
                0xFB,0x32,0x83,0x3C,0x8C,0xC4,0x03,0x01,0x8A,0xC1,0xEA,0xB9,0x21,0xF5,0x6C,0x26,
                0x18,0xA4,0xAF,0x7E,0x38,0xCC,0xC9,0xCF,0x52,0x67,0xAA,0x19,0xFD,0xBA,0x32,0x0C
            };
            info->key_file = key3;
            break;
        }

        case 4: /* other downloaded files */
        default:
            printf("unknown decryption key\n");
            goto fail;
    }

    return 1;
fail:
    return 0;
}

static void create_directories(char* base, char* path) {
    char* directory = strtok(path, "/");
    char* next_directory;
#ifdef _WIN32
    mkdir(base);
#else
    mkdir(base, S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH);
#endif
    while (directory != NULL) {
        next_directory = strtok(NULL, "/");

        strcat(base, "/");
        strncat(base, directory, strlen(directory));

        if (next_directory != NULL) {
#ifdef _WIN32
             mkdir(base);
#else
             mkdir(base, S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH);
#endif

        }

        directory = next_directory;
    }
}

static int parse_cfg(khux_config_t* cfg, int argc, const char* argv[]) {
    if (argc < 1)
        goto fail;

    for (int i = 1; i < argc; i++) {
        if (argv[i][0] != '-') {
            if (cfg->in_path == NULL) {
                cfg->in_path = argv[i];
            }
            else if (cfg->out_path == NULL) {
                cfg->out_path = argv[i];
            }
            else {
                goto fail;
            }

            continue;
        }

        switch(argv[i][1]) {
            case 'k':
                if (i+1 >= argc) goto fail;
                i++;
                cfg->key_type = strtol(argv[i], NULL, 10);
                break;
            case 'w':
                if (i+1 >= argc) goto fail;
                i++;
                cfg->write_from = strtol(argv[i], NULL, 10);
                break;
            case 'W':
                if (i+1 >= argc) goto fail;
                i++;
                cfg->write_max = strtol(argv[i], NULL, 10);
                break;
            case 'l':
                cfg->list_only = 1;
                break;
            case 'n':
                cfg->print_names = 1;
                break;
            case 'd':
                cfg->disable_img = 1;
                break;
            case 'b':
                cfg->enable_bmp = 1;
                break;
            case 's':
                cfg->dump_small = 1;
                break;
            case 'f':
                if (i+1 >= argc) goto fail;
                i++;
                cfg->prefix = argv[i];
                break;
            case 'F':
                if (i+1 >= argc) goto fail;
                i++;
                cfg->suffix = argv[i];
                break;
            default:
                break;
        }
    }
    
    if (cfg->in_path == NULL) {
        goto fail;
    }

    if (cfg->out_path == NULL) {
        strcpy(cfg->out_temp, cfg->in_path);
        char* dot = strrchr(cfg->out_temp, '.');
        if (dot)
            *dot = '\0';
        cfg->out_path = (const char*)cfg->out_temp;
    }

    cfg->out_len = strlen(cfg->out_path);

    if (cfg->list_only)
        cfg->print_names = 1;

    return 1;
fail:
    printf("Usage: %s [options] file [folder]\n", argv[0]);
    printf("KHUX decrypt v3 r3 by bnnm. Options:\n");
    printf(" -l: list files only\n");
    printf(" -n: print filenames\n");
    printf(" -d: disable BGT to PNG conversion (faster)\n");
    //printf(" -b: write BMP instead of PNG\n");
    printf(" -s: dump tiny files (usually just placeholders)\n");
    printf(" -f PREFIX: filter by filename prefix\n");
    printf(" -F SUFFIX: filter by filename suffix\n");
    printf(" -w N: write from file N (to dump updates)\n");
    printf(" -W N: write max N files\n");
    printf(" -k N: force encryption3 key if autodetection fails\n");
    printf("    1: for files inside .apk\n");
    printf("    2: for downloaded files in the 'r' folder\n");
    printf("    3: for saved/cache files?\n");
    return 0;
}


int main(int argc, const char* argv[]) {

    khux_config_t cfg = {0};
    int parse_ok = parse_cfg(&cfg, argc, argv);
    if (!parse_ok) return 0;

    khux_file_t* kfile = kfopen(cfg.in_path);
    if (!kfile) {
        printf("can't open '%s'\n", cfg.in_path);
        return 0;
    }

    bgad_info_t* info = calloc(1, sizeof(bgad_info_t));
    if (!info) {
        printf("can't alloc\n");
        goto done;
    }

    info->cfg = &cfg;

    int key_ok = set_key(kfile, info, cfg.key_type);
    if (!key_ok) goto done;

    read_index(kfile, info);

    char write_path[KHUX_PATH_LIMIT];

    printf("processing...\n");
    while (read_bgad(kfile, info)) {

        info->count++;

        if (!cfg.dump_small && info->is_small)
            continue;

        if (info->cfg->write_from && info->count < info->cfg->write_from)
            continue;

        if ((cfg.prefix != NULL && !starts_with(info->name, cfg.prefix)) ||
            (cfg.suffix != NULL && !ends_with(info->name, cfg.suffix)))
            continue;

        if (cfg.print_names)
            printf("file %08i @%08"PRIx64" %c: %s\n", info->count, info->offset, info->name_origin, info->name);

        if (cfg.list_only)
            continue;

        memset(write_path, 0, sizeof(write_path));
        strncat(write_path, cfg.out_path, cfg.out_len);
        create_directories(write_path, info->name);

        /* don't overwrite files, because some inside big mp4 repeat names */
        FILE* test_file = fopen(write_path, "rb");
        if (test_file) {
            fclose(test_file);

            char* oldext = strrchr(write_path, '.');
            
            char newext[255];
            if (oldext) {
                sprintf(newext, ".%08i%s", info->count, oldext);
                oldext[0] = '\0';
            }
            else {
                sprintf(newext, ".%08i", info->count);
            }
            strcat(write_path, newext);
        }

        FILE* out_file = fopen(write_path, "wb");
        if (!out_file) {
            printf("can't create '%s'\n", write_path);
            goto done;
        }
        fwrite(info->buf, info->buf_size, 1, out_file);
        fclose(out_file);
        
        info->written++;
        
        if (info->written % 10000 == 0)
            printf("%i...\n", info->written);
        
        if (info->cfg->write_max && info->written >= info->cfg->write_max) {
            break;
        }
    }

    printf("done (%i/%i files)\n", info->written, info->count);

done:
    kfclose(kfile);
    free(info->index_file);
    free(info->index_info);
    free(info);
    return 0;
}
