# dumps .ogg from process memory
#
# mainly a demo, for games that decrypt .ogg in memory and reversing their decryption is annoying
# TODO: may not work with processes using +2GB of memory?

# pip install psutil
try:
    import psutil
except:
    print("can't find 'psutil': dumper will only work using PIDs and not process names")
import ctypes
import ctypes.wintypes as wintypes
import sys, os

MIN_OGG_SIZE = 0x100

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', ctypes.c_void_p),
        ('AllocationBase', ctypes.c_void_p),
        ('AllocationProtect', ctypes.c_ulong),
        ('RegionSize', ctypes.c_size_t),
        ('State', ctypes.c_ulong),
        ('Protect', ctypes.c_ulong),
        ('Type', ctypes.c_ulong)
    ]

def dump_ogg(data, start, outname):
    pos = start
    size = 0
    processing = True
        
    while processing:
        page_sync = data[pos + 0x00: pos + 0x05]
        if page_sync != b'OggS\x00':
            break

        page_type = data[pos + 0x05]
        if page_type > 0x7:
            break
        
        # 0x04 is last OggS bitflag, not sure if 0x05 is possible
        if page_type in (0x04, 0x05):
            processing = False

        # lacing values
        packets = data[pos + 0x1A]
        page_size = 0x1b + packets
        for i in range(0, packets):
            packet_size = data[pos + 0x1b + i]
            page_size += packet_size


        pos += page_size
        size += page_size
        if pos >= len(data):
            processing = False

    # ignore small sizes in case only header is found or such
    if size > MIN_OGG_SIZE:
        with open(outname, "wb") as f:
            chunk = data[start : start + size]
            f.write(chunk)

    return size

def region_dump_ogg(data, mbi):
    search_bytes = b'OggS\x00\x02' #start page
    start = 0
    while True:
        start = data.find(search_bytes, start)
        if start < 0:
            return

        outname = "dump_0x%08x.ogg" % (mbi.BaseAddress + start)
        size = dump_ogg(data, start, outname)
        if size > MIN_OGG_SIZE:
            print("Found Ogg at 0x%08X + 0x%08X" % (mbi.BaseAddress + start, size))
        start += size


def read_process_memory(pid):
    PROCESS_ALL_ACCESS = 0x1F0FFF

    process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()

    while ctypes.windll.kernel32.VirtualQueryEx(process_handle, address, ctypes.byref(mbi), ctypes.sizeof(mbi)):
        if mbi.State == 0x1000 and mbi.Protect == 0x04:
            buffer = ctypes.create_string_buffer(mbi.RegionSize)
            bytes_read = ctypes.c_size_t()
            if ctypes.windll.kernel32.ReadProcessMemory(process_handle, mbi.BaseAddress, buffer, mbi.RegionSize, ctypes.byref(bytes_read)):
                data = buffer.raw
                region_dump_ogg(data, mbi)

        address += mbi.RegionSize
        if address >= 0xFFFFFFFF:
            #TODO
            break
    ctypes.windll.kernel32.CloseHandle(process_handle)

def read_process(process):
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if process in proc.info['name'] or process == str(proc.info['pid']):
                read_process_memory(proc.info['pid'])
    except NameError: 
        read_process_memory(int(process))

def main():
    if len(sys.argv) < 2:
        script_name = sys.argv[0]  # The script name
        script_name = os.path.basename(script_name)
        print(f"Usage: {script_name} process-name-or-pid")
        return
    process = sys.argv[1]  # Skip the script name
    read_process(process)

if __name__ == '__main__':
    main()
