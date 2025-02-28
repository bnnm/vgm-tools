#ifndef _MEMMAPPING_
#define _MEMMAPPING_

#include <stdint.h>
#include <stdbool.h>


typedef struct {
    size_t file_size;
    void* file_content;

    void* file;
    void* file_mapping;
    int fd;
} map_t;


bool map_file(map_t* map, const char* filename);
bool unmap_file(map_t* map);

#endif
