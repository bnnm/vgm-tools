#include "memmapping.h"
#include <stdio.h>

//#define MEMMAP_NOOP 1

// TODO: untested on linux (uses memmap to handle streaming, shouldn't be too hard to get it working)
#ifdef WIN32
    #include <windows.h>
#else
    #include <fcntl.h>
    #include <sys/mman.h>
    #include <sys/stat.h>
    #include <unistd.h>
#endif


#ifdef  MEMMAP_NOOP
bool map_file(map_t* map, const char* filename) {
    return false;
}

bool unmap_file(map_t* map) {
    return false;
}

#else
#ifdef WIN32

bool map_file(map_t* map, const char* filename) {

    map->file = CreateFile(filename, GENERIC_READ, 0, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (map->file == INVALID_HANDLE_VALUE) {
        fprintf(stderr, "Error opening file: %lu\n", GetLastError());
        return false;
    }

    map->file_size = GetFileSize(map->file, NULL);
    if (map->file_size == INVALID_FILE_SIZE) {
        fprintf(stderr, "Error getting file size: %lu\n", GetLastError());
        return false;
    }

    map->file_mapping = CreateFileMapping(map->file, NULL, PAGE_READONLY, 0, 0, NULL);
    if (map->file_mapping == NULL) {
        fprintf(stderr, "Error creating file mapping: %lu\n", GetLastError());
        return false;
    }

    map->file_content = MapViewOfFile(map->file_mapping, FILE_MAP_READ, 0, 0, 0);
    if (map->file_content == NULL) {
        fprintf(stderr, "Error mapping view of file: %lu\n", GetLastError());
        return false;
    }

    return true;
}

bool unmap_file(map_t* map) {

    if (map->file_content && !UnmapViewOfFile(map->file_content)) {
        //fprintf(stderr, "Error unmapping view of file: %lu\n", GetLastError());
        return false;
    }

    if (map->file_mapping)
        CloseHandle(map->file_mapping);
    if (map->file)
        CloseHandle(map->file);

    return true;
}
#else

bool map_file(map_t* map, const char* filename) {
    map->fd = open(filename, O_RDONLY);
    if (map->fd == -1)
        return false;

    struct stat sb;
    if (fstat(fd, &sb) == -1)
        return false;
    
    map->file_size = sb.st_size;
    map->file_content = mmap(NULL, map->file_size, PROT_READ, MAP_PRIVATE, map->fd, 0);
    if (map->file_content == MAP_FAILED)
        return false;

    return true;
}

bool unmap_file(map_t* map) {
    if (map->file_content)
        munmap(map->file_content, map->file_size);
    if (map->fd)
        close(map->fd);

    return true;
}
#endif
#endif
