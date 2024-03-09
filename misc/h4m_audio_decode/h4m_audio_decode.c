#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <inttypes.h>
#include <string.h>

/* .h4m (HVQM4 1.3/1.5) audio decoder 0.7
    by hcs with contributions from Nisto/bnnm */

//#define VERBOSE_PRINT

#define HVQM4_AUDIO_IMA_ADPCM  0x00 /* 4-bit IMA ADPCM */
#define HVQM4_AUDIO_PCM        0x01 /* Uncompressed PCM */
#define HVQM4_AUDIO_ADPCM8     0x04 /* 8-bit (A)DPCM */

#define HVQM4_AUDIO  0x00
#define HVQM4_VIDEO  0x01

static uint16_t get_u16_be(uint8_t *buf)
{
    uint16_t v = 0;
    for (int i = 0; i < 2; i++)
    {
        v <<= 8;
        v |= buf[i];
    }
    return v;
}

static uint32_t get_u32_be(uint8_t *buf)
{
    uint32_t v = 0;
    for (int i = 0; i < 4; i++)
    {
        v <<= 8;
        v |= buf[i];
    }
    return v;
}

static void put_u16_le(uint8_t *buf, uint16_t v)
{
    for (unsigned int i = 0; i < 2; i++)
    {
        buf[i] = v & 0xFF;
        v >>= 8;
    }
}

static void put_u32_le(uint8_t *buf, uint32_t v)
{
    for (unsigned int i = 0; i < 4; i++)
    {
        buf[i] = v & 0xFF;
        v >>= 8;
    }
}

static uint16_t read_u16_be(FILE *infile)
{
    uint8_t buf[2];
    if (2 != fread(buf, 1, 2, infile))
    {
        fprintf(stderr, "read error at 0x%lx\n", ftell(infile));
        exit(EXIT_FAILURE);
    }
    return get_u16_be(buf);
}

static uint32_t read_u32_be(FILE *infile)
{
    uint8_t buf[4];
    if (4 != fread(buf, 1, 4, infile))
    {
        fprintf(stderr, "read error at 0x%lx\n", ftell(infile));
        exit(EXIT_FAILURE);
    }
    return get_u32_be(buf);
}

static void write_u8_be(FILE *outfile, uint8_t v)
{
    uint8_t buf[1];

    buf[0] = v & 0xFF;

    fwrite(buf, 1, 1, outfile);
}

static void write_u16_be(FILE *outfile, uint16_t v)
{
    uint8_t buf[2];

    buf[0] = (v >> 8) & 0xFF;
    buf[1] = (v >> 0) & 0xFF;

    fwrite(buf, 1, 2, outfile);
}

static void write_u32_be(FILE *outfile, uint32_t v)
{
    uint8_t buf[4];

    buf[0] = (v >> 24) & 0xFF;
    buf[1] = (v >> 16) & 0xFF;
    buf[2] = (v >>  8) & 0xFF;
    buf[3] = (v >>  0) & 0xFF;

    fwrite(buf, 1, 4, outfile);
}

static int16_t clamp16(int32_t v)
{
    if (v > INT16_MAX) return INT16_MAX;
    else if (v < INT16_MIN) return INT16_MIN;
    return v;
}

/* substitute extension with replacement string */
char *subext(char *path, const char *rep)
{
    int i, s = 0;
    char *out;

    /* scan from start up to basename (this ensures we're not grabbing something
       that looks like an extension at the end of a folder name or something) */
    for (i = 0; path[i]; i++) {
        if (path[i] == '/' || path[i] == '\\') {
            s = i + 1;
        }
    }

    /* scan from basename up to extension */
    for (i = s; path[i]; i++) {
        if (path[i] == '.') {
            s = i;
        }
    }

    /* no extension; get full path */
    if (path[s] != '.') {
        s = i;
    }

    out = malloc(s + strlen(rep) + 1);

    if (!out) return NULL;

    memcpy(out, path, s);

    strcpy(out + s, rep);

    return out;
}

struct audio_state
{
    struct
    {
        int16_t hist;
        int8_t idx;
    } *ch;
};

const int8_t IMA_IndexTable[89][8] =
{
    {  0,  0,  0,  0,  2,  4,  6,  8 },
    {  0,  0,  0,  0,  3,  5,  7,  9 },
    {  1,  1,  1,  1,  4,  6,  8, 10 },
    {  2,  2,  2,  2,  5,  7,  9, 11 },
    {  3,  3,  3,  3,  6,  8, 10, 12 },
    {  4,  4,  4,  4,  7,  9, 11, 13 },
    {  5,  5,  5,  5,  8, 10, 12, 14 },
    {  6,  6,  6,  6,  9, 11, 13, 15 },
    {  7,  7,  7,  7, 10, 12, 14, 16 },
    {  8,  8,  8,  8, 11, 13, 15, 17 },
    {  9,  9,  9,  9, 12, 14, 16, 18 },
    { 10, 10, 10, 10, 13, 15, 17, 19 },
    { 11, 11, 11, 11, 14, 16, 18, 20 },
    { 12, 12, 12, 12, 15, 17, 19, 21 },
    { 13, 13, 13, 13, 16, 18, 20, 22 },
    { 14, 14, 14, 14, 17, 19, 21, 23 },
    { 15, 15, 15, 15, 18, 20, 22, 24 },
    { 16, 16, 16, 16, 19, 21, 23, 25 },
    { 17, 17, 17, 17, 20, 22, 24, 26 },
    { 18, 18, 18, 18, 21, 23, 25, 27 },
    { 19, 19, 19, 19, 22, 24, 26, 28 },
    { 20, 20, 20, 20, 23, 25, 27, 29 },
    { 21, 21, 21, 21, 24, 26, 28, 30 },
    { 22, 22, 22, 22, 25, 27, 29, 31 },
    { 23, 23, 23, 23, 26, 28, 30, 32 },
    { 24, 24, 24, 24, 27, 29, 31, 33 },
    { 25, 25, 25, 25, 28, 30, 32, 34 },
    { 26, 26, 26, 26, 29, 31, 33, 35 },
    { 27, 27, 27, 27, 30, 32, 34, 36 },
    { 28, 28, 28, 28, 31, 33, 35, 37 },
    { 29, 29, 29, 29, 32, 34, 36, 38 },
    { 30, 30, 30, 30, 33, 35, 37, 39 },
    { 31, 31, 31, 31, 34, 36, 38, 40 },
    { 32, 32, 32, 32, 35, 37, 39, 41 },
    { 33, 33, 33, 33, 36, 38, 40, 42 },
    { 34, 34, 34, 34, 37, 39, 41, 43 },
    { 35, 35, 35, 35, 38, 40, 42, 44 },
    { 36, 36, 36, 36, 39, 41, 43, 45 },
    { 37, 37, 37, 37, 40, 42, 44, 46 },
    { 38, 38, 38, 38, 41, 43, 45, 47 },
    { 39, 39, 39, 39, 42, 44, 46, 48 },
    { 40, 40, 40, 40, 43, 45, 47, 49 },
    { 41, 41, 41, 41, 44, 46, 48, 50 },
    { 42, 42, 42, 42, 45, 47, 49, 51 },
    { 43, 43, 43, 43, 46, 48, 50, 52 },
    { 44, 44, 44, 44, 47, 49, 51, 53 },
    { 45, 45, 45, 45, 48, 50, 52, 54 },
    { 46, 46, 46, 46, 49, 51, 53, 55 },
    { 47, 47, 47, 47, 50, 52, 54, 56 },
    { 48, 48, 48, 48, 51, 53, 55, 57 },
    { 49, 49, 49, 49, 52, 54, 56, 58 },
    { 50, 50, 50, 50, 53, 55, 57, 59 },
    { 51, 51, 51, 51, 54, 56, 58, 60 },
    { 52, 52, 52, 52, 55, 57, 59, 61 },
    { 53, 53, 53, 53, 56, 58, 60, 62 },
    { 54, 54, 54, 54, 57, 59, 61, 63 },
    { 55, 55, 55, 55, 58, 60, 62, 64 },
    { 56, 56, 56, 56, 59, 61, 63, 65 },
    { 57, 57, 57, 57, 60, 62, 64, 66 },
    { 58, 58, 58, 58, 61, 63, 65, 67 },
    { 59, 59, 59, 59, 62, 64, 66, 68 },
    { 60, 60, 60, 60, 63, 65, 67, 69 },
    { 61, 61, 61, 61, 64, 66, 68, 70 },
    { 62, 62, 62, 62, 65, 67, 69, 71 },
    { 63, 63, 63, 63, 66, 68, 70, 72 },
    { 64, 64, 64, 64, 67, 69, 71, 73 },
    { 65, 65, 65, 65, 68, 70, 72, 74 },
    { 66, 66, 66, 66, 69, 71, 73, 75 },
    { 67, 67, 67, 67, 70, 72, 74, 76 },
    { 68, 68, 68, 68, 71, 73, 75, 77 },
    { 69, 69, 69, 69, 72, 74, 76, 78 },
    { 70, 70, 70, 70, 73, 75, 77, 79 },
    { 71, 71, 71, 71, 74, 76, 78, 80 },
    { 72, 72, 72, 72, 75, 77, 79, 81 },
    { 73, 73, 73, 73, 76, 78, 80, 82 },
    { 74, 74, 74, 74, 77, 79, 81, 83 },
    { 75, 75, 75, 75, 78, 80, 82, 84 },
    { 76, 76, 76, 76, 79, 81, 83, 85 },
    { 77, 77, 77, 77, 80, 82, 84, 86 },
    { 78, 78, 78, 78, 81, 83, 85, 87 },
    { 79, 79, 79, 79, 82, 84, 86, 88 },
    { 80, 80, 80, 80, 83, 85, 87, 88 },
    { 81, 81, 81, 81, 84, 86, 88, 88 },
    { 82, 82, 82, 82, 85, 87, 88, 88 },
    { 83, 83, 83, 83, 86, 88, 88, 88 },
    { 84, 84, 84, 84, 87, 88, 88, 88 },
    { 85, 85, 85, 85, 88, 88, 88, 88 },
    { 86, 86, 86, 86, 88, 88, 88, 88 },
    { 87, 87, 87, 87, 88, 88, 88, 88 }
};

const int32_t IMA_Steps[89][8] =
{
    {    0,     1,     3,     4,     7,     8,    10,    11 },
    {    1,     3,     5,     7,     9,    11,    13,    15 },
    {    1,     3,     5,     7,    10,    12,    14,    16 },
    {    1,     3,     6,     8,    11,    13,    16,    18 },
    {    1,     3,     6,     8,    12,    14,    17,    19 },
    {    1,     4,     7,    10,    13,    16,    19,    22 },
    {    1,     4,     7,    10,    14,    17,    20,    23 },
    {    1,     4,     8,    11,    15,    18,    22,    25 },
    {    2,     6,    10,    14,    18,    22,    26,    30 },
    {    2,     6,    10,    14,    19,    23,    27,    31 },
    {    2,     6,    11,    15,    21,    25,    30,    34 },
    {    2,     7,    12,    17,    23,    28,    33,    38 },
    {    2,     7,    13,    18,    25,    30,    36,    41 },
    {    3,     9,    15,    21,    28,    34,    40,    46 },
    {    3,    10,    17,    24,    31,    38,    45,    52 },
    {    3,    10,    18,    25,    34,    41,    49,    56 },
    {    4,    12,    21,    29,    38,    46,    55,    63 },
    {    4,    13,    22,    31,    41,    50,    59,    68 },
    {    5,    15,    25,    35,    46,    56,    66,    76 },
    {    5,    16,    27,    38,    50,    61,    72,    83 },
    {    6,    18,    31,    43,    56,    68,    81,    93 },
    {    6,    19,    33,    46,    61,    74,    88,   101 },
    {    7,    22,    37,    52,    67,    82,    97,   112 },
    {    8,    24,    41,    57,    74,    90,   107,   123 },
    {    9,    27,    45,    63,    82,   100,   118,   136 },
    {   10,    30,    50,    70,    90,   110,   130,   150 },
    {   11,    33,    55,    77,    99,   121,   143,   165 },
    {   12,    36,    60,    84,   109,   133,   157,   181 },
    {   13,    39,    66,    92,   120,   146,   173,   199 },
    {   14,    43,    73,   102,   132,   161,   191,   220 },
    {   16,    48,    81,   113,   146,   178,   211,   243 },
    {   17,    52,    88,   123,   160,   195,   231,   266 },
    {   19,    58,    97,   136,   176,   215,   254,   293 },
    {   21,    64,   107,   150,   194,   237,   280,   323 },
    {   23,    70,   118,   165,   213,   260,   308,   355 },
    {   26,    78,   130,   182,   235,   287,   339,   391 },
    {   28,    85,   143,   200,   258,   315,   373,   430 },
    {   31,    94,   157,   220,   284,   347,   410,   473 },
    {   34,   103,   173,   242,   313,   382,   452,   521 },
    {   38,   114,   191,   267,   345,   421,   498,   574 },
    {   42,   126,   210,   294,   379,   463,   547,   631 },
    {   46,   138,   231,   323,   417,   509,   602,   694 },
    {   51,   153,   255,   357,   459,   561,   663,   765 },
    {   56,   168,   280,   392,   505,   617,   729,   841 },
    {   61,   184,   308,   431,   555,   678,   802,   925 },
    {   68,   204,   340,   476,   612,   748,   884,  1020 },
    {   74,   223,   373,   522,   672,   821,   971,  1120 },
    {   82,   246,   411,   575,   740,   904,  1069,  1233 },
    {   90,   271,   452,   633,   814,   995,  1176,  1357 },
    {   99,   298,   497,   696,   895,  1094,  1293,  1492 },
    {  109,   328,   547,   766,   985,  1204,  1423,  1642 },
    {  120,   360,   601,   841,  1083,  1323,  1564,  1804 },
    {  132,   397,   662,   927,  1192,  1457,  1722,  1987 },
    {  145,   436,   728,  1019,  1311,  1602,  1894,  2185 },
    {  160,   480,   801,  1121,  1442,  1762,  2083,  2403 },
    {  176,   528,   881,  1233,  1587,  1939,  2292,  2644 },
    {  194,   582,   970,  1358,  1746,  2134,  2522,  2910 },
    {  213,   639,  1066,  1492,  1920,  2346,  2773,  3199 },
    {  234,   703,  1173,  1642,  2112,  2581,  3051,  3520 },
    {  258,   774,  1291,  1807,  2324,  2840,  3357,  3873 },
    {  284,   852,  1420,  1988,  2556,  3124,  3692,  4260 },
    {  312,   936,  1561,  2185,  2811,  3435,  4060,  4684 },
    {  343,  1030,  1717,  2404,  3092,  3779,  4466,  5153 },
    {  378,  1134,  1890,  2646,  3402,  4158,  4914,  5670 },
    {  415,  1246,  2078,  2909,  3742,  4573,  5405,  6236 },
    {  457,  1372,  2287,  3202,  4117,  5032,  5947,  6862 },
    {  503,  1509,  2516,  3522,  4529,  5535,  6542,  7548 },
    {  553,  1660,  2767,  3874,  4981,  6088,  7195,  8302 },
    {  608,  1825,  3043,  4260,  5479,  6696,  7914,  9131 },
    {  669,  2008,  3348,  4687,  6027,  7366,  8706, 10045 },
    {  736,  2209,  3683,  5156,  6630,  8103,  9577, 11050 },
    {  810,  2431,  4052,  5673,  7294,  8915, 10536, 12157 },
    {  891,  2674,  4457,  6240,  8023,  9806, 11589, 13372 },
    {  980,  2941,  4902,  6863,  8825, 10786, 12747, 14708 },
    { 1078,  3235,  5393,  7550,  9708, 11865, 14023, 16180 },
    { 1186,  3559,  5932,  8305, 10679, 13052, 15425, 17798 },
    { 1305,  3915,  6526,  9136, 11747, 14357, 16968, 19578 },
    { 1435,  4306,  7178, 10049, 12922, 15793, 18665, 21536 },
    { 1579,  4737,  7896, 11054, 14214, 17372, 20531, 23689 },
    { 1737,  5211,  8686, 12160, 15636, 19110, 22585, 26059 },
    { 1911,  5733,  9555, 13377, 17200, 21022, 24844, 28666 },
    { 2102,  6306, 10511, 14715, 18920, 23124, 27329, 31533 },
    { 2312,  6937, 11562, 16187, 20812, 25437, 30062, 34687 },
    { 2543,  7630, 12718, 17805, 22893, 27980, 33068, 38155 },
    { 2798,  8394, 13990, 19586, 25183, 30779, 36375, 41971 },
    { 3077,  9232, 15388, 21543, 27700, 33855, 40011, 46166 },
    { 3385, 10156, 16928, 23699, 30471, 37242, 44014, 50785 },
    { 3724, 11172, 18621, 26069, 33518, 40966, 48415, 55863 },
    { 4095, 12286, 20478, 28669, 36862, 45053, 53245, 61436 }
};

static void decode_ima_adpcm(struct audio_state *state, uint8_t *input, int16_t *output, uint16_t frame_format, uint32_t sample_count, uint8_t channels)
{
    if (frame_format == 1 || frame_format == 3) {
        for (int c = 0; c < channels; c++) {
            state->ch[c].hist = input[0] << 8;
            if (frame_format == 1) {
                state->ch[c].hist |= input[1] & 0x80;
                state->ch[c].idx = input[1] & 0x7F;
                input += 2;
            } else if (frame_format == 3) {
                state->ch[c].hist |= input[1];
                state->ch[c].idx = input[2];
                input += 3;
            }
        }

        for (int c = channels - 1; c >= 0; c--) {
            put_u16_le((uint8_t*)(output++), state->ch[c].hist);
        }

        --sample_count;
    }

    int c = channels - 1;

    while (sample_count > 0) {
        uint8_t byte = *input++;
        for (int i = 0; i < 2; i++) {
            uint8_t sign = byte & 0x08;
            uint8_t index = byte & 0x07;

            if (sign) {
                state->ch[c].hist = clamp16(((int32_t)(state->ch[c].hist)) - IMA_Steps[state->ch[c].idx][index]);
            } else {
                state->ch[c].hist = clamp16(((int32_t)(state->ch[c].hist)) + IMA_Steps[state->ch[c].idx][index]);
            }

            state->ch[c].idx = IMA_IndexTable[state->ch[c].idx][index];

            put_u16_le((uint8_t*)(output++), state->ch[c].hist);

            if (c-- <= 0) {
                c = channels - 1;
                --sample_count;
            }

            byte >>= 4;
        }
    }
}

const int32_t adpcm8_tables[3][256] = 
{
    {
        0, 4, 8, 12, 16, 20, 24, 29, 35, 40, 46, 52, 58, 65, 72, 80, 88, 96,
        105, 115, 125, 135, 146, 158, 170, 183, 197, 211, 227, 243, 260, 278,
        297, 317, 338, 360, 384, 409, 435, 463, 493, 524, 557, 591, 628, 667,
        707, 750, 796, 844, 895, 948, 1005, 1064, 1127, 1194, 1264, 1338, 1416,
        1499, 1586, 1678, 1776, 1879, 1987, 2102, 2223, 2350, 2485, 2628, 2778,
        2937, 3105, 3282, 3469, 3666, 3875, 4095, 4327, 4573, 4832, 5105, 5394,
        5699, 6021, 6361, 6720, 7099, 7500, 7923, 8369, 8840, 9338, 9864, 10419,
        11004, 11623, 12276, 12966, 13694, 14463, 15275, 16132, 17038, 17994,
        19003, 20068, 21194, 22382, 23637, 24961, 26360, 27837, 29397, 31044,
        32783, 34619, 36557, 38604, 40765, 43048, 45457, 48002, 50689, 53526,
        56521, 59684, 63000, 0, -63000, -59684, -56521, -53526, -50689, -48002,
        -45457, -43048, -40765, -38604, -36557, -34619, -32783, -31044, -29397,
        -27837, -26360, -24961, -23637, -22382, -21194, -20068, -19003, -17994,
        -17038, -16132, -15275, -14463, -13694, -12966, -12276, -11623, -11004,
        -10419, -9864, -9338, -8840, -8369, -7923, -7500, -7099, -6720, -6361,
        -6021, -5699, -5394, -5105, -4832, -4573, -4327, -4095, -3875, -3666,
        -3469, -3282, -3105, -2937, -2778, -2628, -2485, -2350, -2223, -2102,
        -1987, -1879, -1776, -1678, -1586, -1499, -1416, -1338, -1264, -1194,
        -1127, -1064, -1005, -948, -895, -844, -796, -750, -707, -667, -628,
        -591, -557, -524, -493, -463, -435, -409, -384, -360, -338, -317, -297,
        -278, -260, -243, -227, -211, -197, -183, -170, -158, -146, -135, -125,
        -115, -105, -96, -88, -80, -72, -65, -58, -52, -46, -40, -35, -29, -24,
        -20, -16, -12, -8, -4
    },

    {
        0, 2, 4, 6, 8, 10, 12, 15, 17, 20, 23, 26, 29, 33, 36, 40, 44, 48, 53,
        57, 62, 68, 73, 79, 85, 92, 98, 106, 114, 122, 130, 139, 149, 159, 169,
        180, 192, 205, 218, 232, 246, 262, 278, 296, 314, 334, 354, 375, 398,
        422, 448, 474, 502, 532, 564, 597, 632, 669, 708, 750, 793, 839, 888,
        939, 994, 1051, 1112, 1175, 1243, 1314, 1389, 1469, 1553, 1641, 1735,
        1833, 1937, 2047, 2164, 2287, 2416, 2553, 2697, 2850, 3011, 3181, 3360,
        3550, 3750, 3961, 4184, 4420, 4669, 4932, 5209, 5502, 5812, 6138, 6483,
        6847, 7231, 7637, 8066, 8519, 8997, 9502, 10034, 10597, 11191, 11819,
        12481, 13180, 13919, 14698, 15522, 16391, 17309, 18279, 19302, 20383,
        21524, 22729, 24001, 25345, 26763, 28261, 29842, 31500, 0, -31500,
        -29842, -28261, -26763, -25345, -24001, -22729, -21524, -20383, -19302,
        -18279, -17309, -16391, -15522, -14698, -13919, -13180, -12481, -11819,
        -11191, -10597, -10034, -9502, -8997, -8519, -8066, -7637, -7231, -6847,
        -6483, -6138, -5812, -5502, -5209, -4932, -4669, -4420, -4184, -3961,
        -3750, -3550, -3360, -3181, -3011, -2850, -2697, -2553, -2416, -2287,
        -2164, -2047, -1937, -1833, -1735, -1641, -1553, -1469, -1389, -1314,
        -1243, -1175, -1112, -1051, -994, -939, -888, -839, -793, -750, -708,
        -669, -632, -597, -564, -532, -502, -474, -448, -422, -398, -375, -354,
        -334, -314, -296, -278, -262, -246, -232, -218, -205, -192, -180, -169,
        -159, -149, -139, -130, -122, -114, -106, -98, -92, -85, -79, -73, -68,
        -62, -57, -53, -48, -44, -40, -36, -33, -29, -26, -23, -20, -17, -15,
        -12, -10, -8, -6, -4, -2
    },

    {
        0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 12, 13, 15, 17, 18, 20, 22, 24, 27, 29,
        31, 34, 37, 39, 43, 46, 49, 53, 57, 61, 65, 70, 74, 79, 85, 90, 96, 103,
        109, 116, 123, 131, 139, 148, 157, 167, 177, 188, 199, 211, 224, 237,
        251, 266, 282, 298, 316, 334, 354, 375, 397, 420, 444, 470, 497, 526,
        556, 588, 621, 657, 695, 734, 776, 821, 868, 917, 969, 1024, 1082, 1143,
        1208, 1277, 1349, 1425, 1505, 1590, 1680, 1775, 1875, 1981, 2092, 2210,
        2335, 2466, 2605, 2751, 2906, 3069, 3241, 3423, 3616, 3819, 4033, 4260,
        4499, 4751, 5017, 5298, 5596, 5910, 6241, 6590, 6959, 7349, 7761, 8196,
        8655, 9140, 9651, 10191, 10762, 11364, 12001, 12673, 13382, 14130,
        14921, 15750, 0, -15750, -14921, -14130, -13382, -12673, -12001, -11364,
        -10762, -10191, -9651, -9140, -8655, -8196, -7761, -7349, -6959, -6590,
        -6241, -5910, -5596, -5298, -5017, -4751, -4499, -4260, -4033, -3819,
        -3616, -3423, -3241, -3069, -2906, -2751, -2605, -2466, -2335, -2210,
        -2092, -1981, -1875, -1775, -1680, -1590, -1505, -1425, -1349, -1277,
        -1208, -1143, -1082, -1024, -969, -917, -868, -821, -776, -734, -695,
        -657, -621, -588, -556, -526, -497, -470, -444, -420, -397, -375, -354,
        -334, -316, -298, -282, -266, -251, -237, -224, -211, -199, -188, -177,
        -167, -157, -148, -139, -131, -123, -116, -109, -103, -96, -90, -85,
        -79, -74, -70, -65, -61, -57, -53, -49, -46, -43, -39, -37, -34, -31,
        -29, -27, -24, -22, -20, -18, -17, -15, -13, -12, -10, -9, -7, -6, -5,
        -4, -3, -2, -1
    }
};

static void decode_adpcm8(struct audio_state *state, uint8_t *input, int16_t *output, uint16_t frame_format, uint32_t sample_count, uint8_t channels)
{
    if (frame_format & 0x80) {
        for (int c = 0; c < channels; c++) {
            state->ch[c].hist = (*input++ << 8) | *input++;
        }
    }

    while (sample_count-- > 0) {
        for (int c = 0; c < channels; c++) {
            state->ch[c].hist = clamp16(((int32_t)(state->ch[c].hist)) + adpcm8_tables[frame_format & 3][*input++]);
        }

        for (int c = channels - 1; c >= 0; c--) {
            put_u16_le((uint8_t*)(output++), state->ch[c].hist);
        }
    }
}

static void decode_pcm(uint8_t *input, int16_t *output, uint32_t sample_count, uint8_t channels)
{
    while (sample_count-- > 0) {
        for (int c = 0; c < channels; c++) {
            put_u16_le((uint8_t*)(output++), (*input++ << 8) | *input++);
        }
    }
}

const char HVQM4_13_magic[16] = "HVQM4 1.3";
const char HVQM4_15_magic[16] = "HVQM4 1.5";

struct HVQM4_header
{
    enum
    {
        HVQM4_13,
        HVQM4_15,
    } version;

    uint32_t header_size;          /* 0x10-0x13 */
    uint32_t body_size;            /* 0x14-0x17 */
    uint32_t blocks;               /* 0x18-0x1B */

    uint32_t video_frames;         /* 0x1C-0x1F */
    uint32_t audio_frames;         /* 0x20-0x23 */

    uint32_t frame_interval;       /* 0x24-0x27 */
    uint32_t max_video_frame_size; /* 0x28-0x2B */

    uint32_t max_sp_packets;       /* 0x2C-0x2F (0) */
    uint32_t max_audio_frame_size; /* 0x30-0x33 */

    uint16_t hres;                 /* 0x34-0x35 */
    uint16_t vres;                 /* 0x36-0x37 */
    uint8_t  h_srate;              /* 0x38 */
    uint8_t  v_srate;              /* 0x39 */

    uint8_t  video_mode;           /* 0x3A (0 or 0x12) */
    uint8_t  user_defined;         /* 0x3B (0) */

    uint8_t  audio_channels;       /* 0x3C */
    uint8_t  audio_bitdepth;       /* 0x3D */
    uint8_t  audio_format;         /* 0x3E */
    uint8_t  audio_extra_tracks;   /* 0x3F */
    uint32_t audio_srate;          /* 0x40-0x43 */
};

static void load_header(struct HVQM4_header *header, uint8_t *raw_header)
{
    if (!memcmp(HVQM4_13_magic, &raw_header[0], 16)) {
        header->version = HVQM4_13;
    } else if (!memcmp(HVQM4_15_magic, &raw_header[0], 16)) {
        header->version = HVQM4_15;
    } else {
        fprintf(stderr, "does not appear to be a HVQM4 file\n");
        exit(EXIT_FAILURE);
    }

    header->header_size = get_u32_be(&raw_header[0x10]);
    header->body_size = get_u32_be(&raw_header[0x14]);

    header->blocks = get_u32_be(&raw_header[0x18]);

    header->video_frames = get_u32_be(&raw_header[0x1C]);
    header->audio_frames = get_u32_be(&raw_header[0x20]);

    header->frame_interval = get_u32_be(&raw_header[0x24]);
    header->max_video_frame_size = get_u32_be(&raw_header[0x28]);

    header->max_sp_packets = get_u32_be(&raw_header[0x2C]);
    header->max_audio_frame_size = get_u32_be(&raw_header[0x30]);

    header->hres = get_u16_be(&raw_header[0x34]);
    header->vres = get_u16_be(&raw_header[0x36]);
    header->h_srate = raw_header[0x38];
    header->v_srate = raw_header[0x39];

    header->video_mode = raw_header[0x3A];
    header->user_defined = raw_header[0x3B];

    header->audio_channels = raw_header[0x3C];
    header->audio_bitdepth = raw_header[0x3D];
    header->audio_format = raw_header[0x3E];
    header->audio_extra_tracks = raw_header[0x3F];
    header->audio_srate = get_u32_be(&raw_header[0x40]);

    if (header->header_size != 0x44) {
        fprintf(stderr, "unexpected header size!\n");
        exit(EXIT_FAILURE);
    }

    if (header->blocks == 0) {
        fprintf(stderr, "zero blocks\n");
        exit(EXIT_FAILURE);
    }

    if (header->audio_frames != 0) {
        if (header->max_audio_frame_size == 0) {
            fprintf(stderr, "expected nonzero audio frame size\n");
            exit(EXIT_FAILURE);
        }

        if (header->audio_channels == 0) {
            fprintf(stderr, "expected nonzero audio channel count\n");
            exit(EXIT_FAILURE);
        }

        if (header->audio_bitdepth != 16 && header->audio_bitdepth != 0) {
            fprintf(stderr, "unexpected audio bitdepth of %i\n", header->audio_bitdepth);
            exit(EXIT_FAILURE);
        }

        if (header->audio_srate == 0) {
            fprintf(stderr, "expected nonzero sample rate\n");
            exit(EXIT_FAILURE);
        }

        switch (header->audio_format & 0x7F) {
            case HVQM4_AUDIO_IMA_ADPCM:
            case HVQM4_AUDIO_PCM:
            case HVQM4_AUDIO_ADPCM8:
                /* okay */
                break;

            default:
                fprintf(stderr, "unrecognized audio format\n");
                exit(EXIT_FAILURE);
                break;
        }
    }
}

void display_header(struct HVQM4_header *header)
{
    if (header->version == HVQM4_13) {
        printf("HVQM4 1.3\n");
    } else if (header->version == HVQM4_15) {
        printf("HVQM4 1.5\n");
    }

    printf("\n");

    printf("Header size              : 0x%"PRIX32"\n", header->header_size);
    printf("Body size                : 0x%"PRIX32"\n", header->body_size);
    printf("Blocks                   : %"PRIu32"\n", header->blocks);
    printf("Frame interval           : %"PRIu32" microseconds\n", header->frame_interval);

    printf("\n");

    printf("Video frame count        : %"PRIu32"\n", header->video_frames);
    printf("Video frame size (max)   : 0x%"PRIX32"\n", header->max_video_frame_size);
    printf("Resolution               : %"PRIu16" x %"PRIu16"\n", header->hres, header->vres);
    printf("Horizontal sampling rate : %"PRIu8"\n", header->h_srate);
    printf("Vertical sampling rate   : %"PRIu8"\n", header->v_srate);

    printf("\n");

    if (header->audio_frames) {
        char *audio_coding = NULL;

        switch (header->audio_format & 0x7F) {
            case HVQM4_AUDIO_IMA_ADPCM : audio_coding =   "4-bit IMA ADPCM"; break;
            case HVQM4_AUDIO_PCM       : audio_coding = "PCM, Uncompressed"; break;
            case HVQM4_AUDIO_ADPCM8    : audio_coding =     "8-bit (A)DPCM"; break;
        }
        if (header->audio_bitdepth == 0) {
            audio_coding =   "AFC ADPCM";
        }

        printf("Audio frame count        : %"PRIu32"\n", header->audio_frames);
        printf("Audio frame size (max)   : 0x%"PRIX32"\n", header->max_audio_frame_size);
        printf("Audio channels           : %"PRIu8"\n", header->audio_channels);
        printf("Audio bitdepth           : %"PRIu8"\n", header->audio_bitdepth);
        printf("Audio extra tracks       : %"PRIu8"\n", header->audio_extra_tracks);
        printf("Audio format             : 0x%02"PRIX8" (%s)\n", header->audio_format, audio_coding);
        printf("Audio sample rate        : %"PRIu32" Hz\n\n", header->audio_srate);
    } else {
        printf("No audio!\n\n");
    }

    printf("max_sp_packets           : 0x%08"PRIX32"\n", header->max_sp_packets);
    printf("video_mode               : 0x%02"PRIX8"\n", header->video_mode);
    printf("user_defined             : 0x%02"PRIX8"\n", header->user_defined);

    printf("\n");
}

void write_header(FILE *file, struct HVQM4_header *header)
{
    if (header->version == HVQM4_13) {
        fwrite(HVQM4_13_magic, 1, 16, file);
    } else if (header->version == HVQM4_15) {
        fwrite(HVQM4_15_magic, 1, 16, file);
    }

    write_u32_be(file, header->header_size);
    write_u32_be(file, header->body_size);
    write_u32_be(file, header->blocks);
    write_u32_be(file, header->video_frames);
    write_u32_be(file, header->audio_frames);
    write_u32_be(file, header->frame_interval);
    write_u32_be(file, header->max_video_frame_size);
    write_u32_be(file, header->max_sp_packets);
    write_u32_be(file, header->max_audio_frame_size);
    write_u16_be(file, header->hres);
    write_u16_be(file, header->vres);
    write_u8_be(file, header->h_srate);
    write_u8_be(file, header->v_srate);
    write_u8_be(file, header->video_mode);
    write_u8_be(file, header->user_defined);
    write_u8_be(file, header->audio_channels);
    write_u8_be(file, header->audio_bitdepth);
    write_u8_be(file, header->audio_format);
    write_u8_be(file, header->audio_extra_tracks);
    write_u32_be(file, header->audio_srate);
}

static void make_wav_header(uint8_t *buf, int32_t sample_count, int32_t sample_rate, int channels)
{
    int32_t bytecount = sample_count * sizeof(int16_t) * channels;

    /* RIFF header */
    memcpy(buf+0x00, "RIFF", 4);

    /* size of RIFF */
    put_u32_le(buf+0x04, bytecount + 0x2C - 8);

    /* WAVE header */
    memcpy(buf+0x08, "WAVE", 4);

    /* WAVE fmt chunk */
    memcpy(buf+0x0C, "fmt ", 4);

    /* size of WAVE fmt chunk */
    put_u32_le(buf+0x10, 0x10);

    /* compression code 1=PCM */
    put_u16_le(buf+0x14, 1);

    /* channel count */
    put_u16_le(buf+0x16, channels);

    /* sample rate */
    put_u32_le(buf+0x18, sample_rate);

    /* bytes per second */
    put_u32_le(buf+0x1C, sample_rate * sizeof(int16_t) * channels);

    /* block align */
    put_u16_le(buf+0x20, sizeof(int16_t) * channels);

    /* significant bits per sample */
    put_u16_le(buf+0x22, sizeof(int16_t) * 8);

    /* PCM has no extra format bytes, so we don't even need to specify a count */

    /* WAVE data chunk */
    memcpy(buf+0x24, "data", 4);

    /* size of WAVE data chunk */
    put_u32_le(buf+0x28, bytecount);
}

int is_audio_frame(uint16_t frame_type, uint16_t frame_format, int first_aud)
{
    if (frame_type == HVQM4_AUDIO) {
        if ( first_aud && frame_format == 1 ) {
            return 1;
        } else if ( first_aud && frame_format == 3 ) {
            return 1;
        } else if ( !first_aud && frame_format == 2 ) {
            return 1;
        }
    }
    return 0;
}

int is_audio_frame_afc(uint16_t frame_type, uint16_t frame_format, int first_aud)
{
    if (frame_type == HVQM4_AUDIO) {
        if ( first_aud && frame_format == 0xFF00 ) {
            return 1;
        }
    }
    return 0;
}

int is_video_frame(uint16_t frame_type, uint16_t frame_format, int first_vid)
{
    if (frame_type == HVQM4_VIDEO) {
        if ( frame_format == 0x10 ) {
            return 1;
        } else if ( !first_vid && frame_format == 0x20 ) {
            return 1;
        } else if ( frame_format == 0x30 ) {
            return 1;
        }
    }
    return 0;
}

static int main_file(int mode, char* inpath);

int main(int argc, char **argv)
{
    printf("h4m 'HVQM4 1.3/1.5' audio decoder 0.7\n");
    printf("by hcs with contributions from Nisto/bnnm\n\n");
    if (argc == 1) {
        fprintf(stderr, "Usage: %s [mode] <file>\n", argv[0]);
        fprintf(stderr, "\n");
        fprintf(stderr, "Modes:\n");
        fprintf(stderr, "-d : Demux audio (strip video frames) [default]\n");
        fprintf(stderr, "-c : Convert audio to WAV\n");
        fprintf(stderr, "-h : Display header info and exit\n");
        exit(EXIT_FAILURE);
    }

    int start = 1;
    int mode = 'd';

    if (strcmp("-d", argv[1]) == 0) {
        mode = 'd';
        start++;
    } else if (strcmp("-c", argv[1]) == 0) {
        mode = 'c';
        start++;
    } else if (strcmp("-h", argv[1]) == 0) {
        mode = 'h';
        start++;
    }

    if (start >= argc) {
        fprintf(stderr, "missing files\n");
        exit(EXIT_FAILURE);
    }

    for (int i = start; i < argc; i++) {
        main_file(mode, argv[i]);
    }
}

static int main_file(int mode, char* inpath) {

    FILE *infile = fopen(inpath, "rb");

    FILE *outfile = NULL;

    if (!infile) {
        fprintf(stderr, "failed opening %s\n", inpath);
        exit(EXIT_FAILURE);
    }

    uint8_t raw_header[0x44];

    if (sizeof(raw_header) != fread(raw_header, 1, sizeof(raw_header), infile)) {
        fprintf(stderr, "failed reading header\n");
        exit(EXIT_FAILURE);
    }

    printf("file: %s\n", inpath);

    struct HVQM4_header header;
    load_header(&header, raw_header);
    display_header(&header);


    if (mode == 'h') {
        fclose(infile);
        return 0;
    } else if (mode != 'c' && mode != 'd') {
        fprintf(stderr, "invalid arguments!\n");
        fclose(infile);
        return 1;
    }

    int is_demux = mode == 'd';

    if (header.audio_bitdepth == 0 && !is_demux) {
        fprintf(stderr, "can't decode AFC codec (demux only)\n");
        exit(EXIT_FAILURE);
    }

    if (header.audio_frames == 0) {
        printf("this video contains no audio!\n");
        fclose(infile);
        return -1;
    }

    uint8_t *input = calloc(header.max_audio_frame_size, sizeof(uint8_t));

    if (!input) {
        fprintf(stderr, "could not allocate input buffer!\n");
        exit(EXIT_FAILURE);
    }

    int16_t *decbuf = NULL;

    struct { 
        struct {
            FILE *f;
            char *path;
            struct audio_state audio_state;
        } *track;
    } wavstreams = { 0 };

    int total_tracks = 1 + header.audio_extra_tracks;

    if (is_demux) {
        outfile = fopen(subext(inpath, ".audio.h4m"), "wb");

        if (!outfile) {
            fprintf(stderr, "failed creating output file!\n");
            exit(EXIT_FAILURE);
        }

        if (sizeof(raw_header) != fwrite(&raw_header, 1, sizeof(raw_header), outfile)) {
            fprintf(stderr, "failing writing temporary header to output file\n");
            exit(EXIT_FAILURE);
        }
    } else {
        decbuf = calloc(header.max_audio_frame_size, sizeof(int16_t) * header.audio_channels);

        if (!decbuf) {
            fprintf(stderr, "could not allocate output buffer!\n");
            exit(EXIT_FAILURE);
        }

        wavstreams.track = calloc(total_tracks, sizeof(*wavstreams.track));

        for (int i = 0; i < total_tracks; i++) {
            char ext[8];

            if (total_tracks > 1) {
                sprintf(ext, "_%02d.wav", i);
            } else {
                strcpy(ext, ".wav");
            }

            wavstreams.track[i].path = subext(inpath, &ext[0]);

            if (!wavstreams.track[i].path) {
                fprintf(stderr, "failed building output path for track %d\n", i);
                exit(EXIT_FAILURE);
            }

            wavstreams.track[i].f = fopen(wavstreams.track[i].path, "wb");

            if (!wavstreams.track[i].f) {
                fprintf(stderr, "failed creating output file for track %d\n", i);
                exit(EXIT_FAILURE);
            }

            if (0x2C != fwrite(decbuf, 1, 0x2C, wavstreams.track[i].f)) {
                fprintf(stderr, "failed writing temporary header for track %d\n", i);
                exit(EXIT_FAILURE);
            }
        }
    }

    uint32_t block_count = 0;
    uint32_t non_audio_blocks = 0;
    uint32_t total_aud_frames = 0;
    uint32_t total_vid_frames = 0;
    uint32_t total_sample_count = 0;

    long last_block_size = 0;
    long last_outblock_size = 0;

    while (block_count++ < header.blocks) {
        const long block_start = ftell(infile);
        long outblock_start = block_start;

        if (!is_demux) {
            for (int i = 0; i < total_tracks; i++) {
                wavstreams.track[i].audio_state.ch = calloc(
                    header.audio_channels, sizeof(*wavstreams.track[i].audio_state.ch)
                );
            }
        }

        uint32_t prev_block_size = read_u32_be(infile);
        if (prev_block_size != last_block_size) {
            fprintf(stderr, "last block size mismatch at 0x%lX (value=%x vs calc=%x)\n", ftell(infile), prev_block_size, last_block_size);
            exit(EXIT_FAILURE);
        }

        const uint32_t expected_block_size = read_u32_be(infile);
        const uint32_t expected_vid_frame_count = read_u32_be(infile);
        const uint32_t expected_aud_frame_count = read_u32_be(infile);
        const uint32_t block_header_flags = read_u32_be(infile); /* 8b flags + 24b padding **/

        if (is_demux && expected_aud_frame_count != 0) {
            outblock_start = ftell(outfile);
            write_u32_be(outfile, last_outblock_size);
        }

        /* flags specifies block type (01="closed" block/EOS?, 02="broken" block?, 00=some Bomberman Jetters files) */
        if (block_header_flags != 0 && block_header_flags != 0x01000000) {
            fprintf(stderr, "unexpected value at end of block header (0x%lX)\n", ftell(infile));
            exit(EXIT_FAILURE);
        }

        const long data_start = ftell(infile);
        long outdata_start = data_start;

        if (is_demux && expected_aud_frame_count > 0) {
            write_u32_be(outfile, 0);
            write_u32_be(outfile, 0);
            write_u32_be(outfile, expected_aud_frame_count);
            write_u32_be(outfile, block_header_flags);
            outdata_start = ftell(outfile);
        }

#ifdef VERBOSE_PRINT
        printf("block %d starts at 0x%lx, length 0x%"PRIx32"\n", (int)block_count, block_start, expected_block_size);
#endif

        int first_vid = 1, first_aud = 1, block_sample_count = 0;
        uint32_t vid_frame_count = 0, aud_frame_count = 0;

        while (aud_frame_count < expected_aud_frame_count || vid_frame_count < expected_vid_frame_count) {
            uint16_t frame_type = read_u16_be(infile);
            uint16_t frame_format = read_u16_be(infile);
            uint32_t frame_size = read_u32_be(infile);

#ifdef VERBOSE_PRINT
            printf("frame id 0x%"PRIx16"/0x%"PRIx16", size 0x%"PRIx32"\n", frame_type, frame_format, frame_size);
#endif

            if ( is_audio_frame( frame_type, frame_format, first_aud ) ) {
                uint32_t samples = read_u32_be(infile);

                if (is_demux) {
                    write_u16_be(outfile, frame_type);
                    write_u16_be(outfile, frame_format);
                    write_u32_be(outfile, frame_size);
                    write_u32_be(outfile, samples);
                }

                uint32_t audio_bytes = frame_size - 4;

                if (header.audio_format & 0x80) {
                    samples /= 2;
                }

                if (header.audio_extra_tracks && audio_bytes % total_tracks != 0) {
                    fprintf(stderr, "audio bytes not divisible track count (0x%lX)\n", ftell(infile));
                    exit(EXIT_FAILURE);
                }

                if (audio_bytes != fread(input, sizeof(uint8_t), audio_bytes, infile)) {
                    fprintf(stderr, "failed reading %"PRIu32" bytes (0x%lX)\n", audio_bytes, ftell(infile));
                    exit(EXIT_FAILURE);
                }

                if (is_demux) {
                    if (audio_bytes != fwrite(input, sizeof(uint8_t), audio_bytes, outfile)) {
                        fprintf(stderr, "failed writing %"PRIu32" bytes (0x%lX)\n", audio_bytes, ftell(outfile));
                        exit(EXIT_FAILURE);
                    }
                } else {
                    for (int i = 0; i < total_tracks; i++) {
                        switch (header.audio_format & 0x7F) {
                            case HVQM4_AUDIO_IMA_ADPCM:
                                decode_ima_adpcm(&wavstreams.track[i].audio_state, &input[audio_bytes/total_tracks*i], decbuf, frame_format, samples, header.audio_channels);
                                break;
                            case HVQM4_AUDIO_PCM:
                                decode_pcm(&input[audio_bytes/total_tracks*i], decbuf, samples, header.audio_channels);
                                break;
                            case HVQM4_AUDIO_ADPCM8:
                                decode_adpcm8(&wavstreams.track[i].audio_state, &input[audio_bytes/total_tracks*i], decbuf, frame_format, samples, header.audio_channels);
                                break;
                        }

                        if (samples != fwrite(decbuf, sizeof(int16_t) * header.audio_channels, samples, wavstreams.track[i].f)) {
                            fprintf(stderr, "failed writing %"PRIu32" samples to track %d (0x%lX)\n", samples, i, ftell(wavstreams.track[i].f));
                            exit(EXIT_FAILURE);
                        }
                    }
                }

                first_aud = 0;
                block_sample_count += samples;
                aud_frame_count ++;
                total_aud_frames ++;

#ifdef VERBOSE_PRINT
                printf("0x%lx: audio frame %d/%d (%d) (%d samples)\n", audio_started, (int)aud_frame_count, (int)expected_aud_frame_count, (int)total_aud_frames, samples);
#endif
            } else if ( is_audio_frame_afc( frame_type, frame_format, first_aud ) ) {

                if (is_demux) {
                    write_u16_be(outfile, frame_type);
                    write_u16_be(outfile, frame_format);
                    write_u32_be(outfile, frame_size);
                }

                uint32_t audio_bytes = frame_size;

                if (audio_bytes != fread(input, sizeof(uint8_t), audio_bytes, infile)) {
                    fprintf(stderr, "failed reading %"PRIu32" bytes (0x%lX)\n", audio_bytes, ftell(infile));
                    exit(EXIT_FAILURE);
                }

                if (is_demux) {
                    if (audio_bytes != fwrite(input, sizeof(uint8_t), audio_bytes, outfile)) {
                        fprintf(stderr, "failed writing %"PRIu32" bytes (0x%lX)\n", audio_bytes, ftell(outfile));
                        exit(EXIT_FAILURE);
                    }
                }

                first_aud = 0;
                //block_sample_count += samples;
                aud_frame_count ++;
                total_aud_frames ++;

#ifdef VERBOSE_PRINT
                printf("0x%lx: audio frame %d/%d (%d)\n", audio_started, (int)aud_frame_count, (int)expected_aud_frame_count, (int)total_aud_frames);
#endif
            } else if ( is_video_frame( frame_type, frame_format, first_vid ) ) {
                first_vid = 0;
                vid_frame_count ++;
                total_vid_frames ++;

#ifdef VERBOSE_PRINT
                printf("video frame %d/%d (%d)\n", (int)vid_frame_count, (int)expected_vid_frame_count, (int)total_vid_frames);
#endif

                if (-1 == fseek(infile, frame_size, SEEK_CUR)) {
                    fprintf(stderr, "video frame %"PRIu32" seek error\n", total_vid_frames);
                    exit(EXIT_FAILURE);
                }
            } else {
                fprintf(stderr, "unexpected frame id at %08lx\n", ftell(infile));
                exit(EXIT_FAILURE);
            }
        }

        if (expected_aud_frame_count != aud_frame_count || expected_vid_frame_count != vid_frame_count) {
            fprintf(stderr, "frame count mismatch\n");
            exit(EXIT_FAILURE);
        }

#ifdef VERBOSE_PRINT
        printf("block %d ended at 0x%lx (%d samples)\n", (int)block_count, ftell(infile), block_sample_count);
#endif

        if (ftell(infile) != (data_start+expected_block_size)) {
            fprintf(stderr, "block size mismatch\n");
            exit(EXIT_FAILURE);
        }

        total_sample_count += block_sample_count;

        last_block_size = ftell(infile) - block_start;
        if (header.audio_bitdepth == 0) { /* pikmin block sizes don't include header */
            last_block_size -= 0x14;
        }

        if (is_demux) {
            last_outblock_size = ftell(outfile) - outblock_start;
            if (header.audio_bitdepth == 0) { /* pikmin block sizes don't include header */
                last_outblock_size -= 0x14;
            }

            /* update expected block size */
            if (aud_frame_count > 0) {
                const long outblock_size = ftell(outfile) - outdata_start;

                fseek(outfile, outblock_start+4, SEEK_SET);
                write_u32_be(outfile, outblock_size);
                fseek(outfile, 0, SEEK_END);
            } else {
                non_audio_blocks += 1;
            }
        } else {
            for (int i = 0; i < total_tracks; i++) {
                free(wavstreams.track[i].audio_state.ch);
            }
        }
    }

    if (total_aud_frames != header.audio_frames || total_vid_frames != header.video_frames) {
        fprintf(stderr, "total frame count mismatch\n");
        exit(EXIT_FAILURE);
    }

    if (!is_demux) {
        printf("%"PRIu32" samples\n", total_sample_count);
    }

    free(input);

    if (is_demux) {
        header.body_size = ftell(outfile) - 0x44;
        header.blocks -= non_audio_blocks;
        header.video_frames = 0;
        header.max_video_frame_size = 0;
        header.hres = 0;
        header.vres = 0;
        header.h_srate = 0;
        header.v_srate = 0;
        fseek(outfile, 0, SEEK_SET);
        write_header(outfile, &header);
        fclose(outfile);
    } else {
        uint8_t wav_header[0x2C];

        free(decbuf);

        /* finalize output */
        for (int i = 0; i < total_tracks; i++) {
            make_wav_header(wav_header, total_sample_count, header.audio_srate, header.audio_channels);

            fseek(wavstreams.track[i].f, 0, SEEK_SET);

            if (sizeof(wav_header) != fwrite(&wav_header, 1, sizeof(wav_header), wavstreams.track[i].f)) {
                fprintf(stderr, "could not updating WAV header\n");
                exit(EXIT_FAILURE);
            }

            if (EOF == fclose(wavstreams.track[i].f)) {
                fprintf(stderr, "could not close output file for track %d\n", i);
                exit(EXIT_FAILURE);
            }

            free(wavstreams.track[i].path);
        }
    }

    fclose(infile);

    printf("done!\n\n");

    return 0;
}
