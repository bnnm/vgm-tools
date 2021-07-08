/* ffc - faster file compare
 * quick replacement for Windows' crappy fc.exe.
 * compares file1 and file2, returns errno if files are different
 * (returns on first diff, while fc.exe compares the whole thing).
 */

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>


#define BUFFER_SIZE 0x8000


static void usage(const char* name) {
    fprintf(stderr,"ffc \n\n"
            "Usage: %s (infile1) (infile2)\n"
            ,name);
}


int main(int argc, char** argv) {
    FILE* file1 = NULL;
    FILE* file2 = NULL;
    uint8_t buffer1[BUFFER_SIZE];
    uint8_t buffer2[BUFFER_SIZE];
    size_t filesize1;
    size_t filesize2;
    size_t done = 0;


    if (argc <= 1) {
        usage(argv[0]);
        return -1;
    }

    /* open */
    file1 = fopen(argv[1], "rb");
    if (!file1) goto fail_files;

    file2 = fopen(argv[2], "rb");
    if (!file2) goto fail_files;

    /* sizes */
    if ( fseek(file1, 0, SEEK_END) == -1)
        goto fail_files;
    filesize1 = ftell(file1);
    fseek(file1, 0, SEEK_SET);

    if ( fseek(file2, 0, SEEK_END) == -1)
        return 2;
    filesize2 = ftell(file2);
    fseek(file2, 0, SEEK_SET);

    if (filesize1 != filesize2)
        goto fail_diff;


    /* compare */
    while (done < filesize1) {
        int i;
        size_t read1 = fread(buffer1, sizeof(uint8_t), BUFFER_SIZE, file1);
        size_t read2 = fread(buffer2, sizeof(uint8_t), BUFFER_SIZE, file2);

        if (read1 == 0 || read2 == 0)
            goto fail_diff;

#if 0
        /* fails faster but slower to compare? (fail is less common case) */ 
        for (i = 0; i < read1; i++) {
            if (buffer1[i] != buffer2[i])
                goto fail_diff;
        }
#else
        /* faster to compare but does't fail as fast */
        if (memcmp(buffer1, buffer2, read1) != 0)
            goto fail_diff;
#endif

        done += read1;
    }

    printf("FFC: same file\n");
    fclose(file1);
    fclose(file2);
    errno = 0;
    return 0; /* same */

fail_diff:
    printf("FFC: different file\n");
    fclose(file1);
    fclose(file2);
    errno = 1;
    return 1; /* files are different */

fail_files:
    printf("FFC: file error\n");
    fclose(file1);
    fclose(file2);
    errno = 2;
    return 2; /* cannot find at least one of the files */
}
