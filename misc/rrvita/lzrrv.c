#include <stdio.h>
#include <string.h>

/* Ridge Racer Vita decompressor (simplified LZSS) by bnnm */
int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("LZRRV decoder by bnnm\nUsage: %s infile\n", argv[0]);
        return 1;
    }

    FILE* f_out = NULL;
    FILE* f_in = NULL;

    f_in = fopen(argv[1], "rb");
    if (f_in == NULL) {
        printf("cannot open infile %s", argv[1]);
        goto end;
    }

    char s_out[32768];
    strcpy(s_out, argv[1]);
    strcat(s_out, ".dec");
    f_out = fopen(s_out, "wb+");
    if (f_out == NULL) {
        printf("cannot open outfile %s", s_out);
        goto end;
    }


    unsigned char buf[256] = {0};
    unsigned char buf0[256] = {0};
    int c1,c2;
    while (1) {
        /* get 16b LE command */
        if ((c1 = getc(f_in)) == EOF) break;
        if ((c2 = getc(f_in)) == EOF) break;

        if (c2 == 0xFF) { /* copy uncompressed value */
            int len = c1 + 1; /* tested max is 0x100 */

            int bytes = fread(buf, 1, len, f_in);

            fwrite(buf, 1, bytes, f_out);
        }
        else { /* copy window value */
            int flag = (c2 << 8) | c1;
            int len = ((flag >> 0) & 0x01F) + 3;
            int off = ((flag >> 5) & 0x7FF) + 1;

            /* use file as window, meh */
            fseek(f_out, -off, SEEK_END); 
            int bytes = fread(buf, 1, len, f_out);
            fseek(f_out, 0, SEEK_END);

            fwrite(buf, 1, bytes, f_out);
            if (len != bytes) { /* reading further on 0-init window, happens sometimes */
                fwrite(buf0, 1, len - bytes, f_out);
            }
        }
    }

end:
    fclose(f_in);
    fclose(f_out);
    return 0;
}