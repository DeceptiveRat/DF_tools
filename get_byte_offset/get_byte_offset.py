#!/usr/bin/env python3 

import sys
import io
import getopt

def usage():
    print("usage:", sys.argv[0])
    print("options:")
    print("\t-h: display this help screen")
    print("\t-f <file>: file to search. If this is not provided, stdin is used")
    print("\t-p <pattern>: pattern to search for. Either this or -c must be provided. Enter as hex; e.g. 3ccf10")
    print("\t-s <int>: skip bytes")
    print("\t-l <int>: max length to parse in bytes. Skipped bytes are included. Default: 1,000,000")
    print("\t-c <pattern>,...: complex pattern. Given in <offset:pattern> pair. Offset is relative to start of first pattern. e.g. 0:C0FFEE,16:DEADBEEF")

def matchList(pattern_list, offset, current_buf):
    for pattern_offset, pattern in pattern_list.items():
        start_offset = offset + pattern_offset
        end_offset = start_offset + len(pattern)
        
        # Prevent index out of bounds on truncated data
        if end_offset > len(current_buf):
            return False
            
        if current_buf[start_offset:end_offset] != pattern:
            return False
    
    return True

file_name = ""
search_length = 1000000 # Default from usage
search_pattern = b""
skip_length = 0
pattern_list = {}

try:
    opts, args = getopt.getopt(sys.argv[1:], "hf:l:p:s:c:")
except getopt.GetoptError as err:
    print(err)
    usage()
    sys.exit(2)

for option, argument in opts:
    if option == "-h":
        usage()
        sys.exit()
    elif option == "-f":
        file_name = argument 
    elif option == "-l":
        search_length = int(argument)
    elif option == "-p":
        search_pattern = bytes.fromhex(str(argument))
    elif option == "-s":
        skip_length = int(argument)
    elif option == "-c":
        for _ in argument.split(","):
            offset, pattern = _.split(":")
            pattern_list[int(offset)] = bytes.fromhex(pattern)
    else:
        assert False, "unhandled option"

if search_pattern == b"" and not pattern_list:
    print("Error! Please enter search pattern")
    sys.exit(-1)

# Initialize primary search pattern and format the pattern list
if pattern_list:
    if 0 not in pattern_list:
        # If no offset 0 is provided, use the lowest offset as the base
        base_offset = min(pattern_list.keys())
        search_pattern = pattern_list[base_offset]
        pattern_list = {k - base_offset: v for k, v in pattern_list.items()}
    else:
        search_pattern = pattern_list[0]

# Calculate the maximum extent (in bytes) a complex pattern can reach
max_extent = len(search_pattern) if search_pattern else 0
for offset, pattern in pattern_list.items():
    ext = offset + len(pattern)
    if ext > max_extent:
        max_extent = ext

if pattern_list and 0 in pattern_list:
    pattern_list.pop(0)

# Setup chunking parameters
overlap_size = max_extent - 1
CHUNK_SIZE = max(1024 * 1024, max_extent * 2) # Read in 1MB chunks

global_offset = skip_length

if file_name != "":
    f = open(file_name, 'rb')
    f.seek(skip_length)
else:
    f = sys.stdin.buffer
    # stdin cannot seek, so we must read and discard
    bytes_to_skip = skip_length
    while bytes_to_skip > 0:
        discard_chunk = f.read(min(bytes_to_skip, CHUNK_SIZE))
        if not discard_chunk:
            break
        bytes_to_skip -= len(discard_chunk)

buf = bytearray()

try:
    while True:
        chunk = f.read(CHUNK_SIZE)
        buf.extend(chunk)
        
        if not chunk and len(buf) == 0:
            break
            
        pos = 0
        while True:
            # Search for primary pattern
            pos = buf.find(search_pattern, pos)
            if pos == -1:
                break
                
            actual_offset = global_offset + pos
            
            # Stop if we hit the user-defined length limit
            if actual_offset >= search_length:
                sys.exit(0)
            
            # If the complex pattern extends beyond the current buffer, 
            # and we haven't reached EOF yet, wait for the next chunk to verify.
            if pos + max_extent > len(buf) and chunk:
                break
            
            # Match remaining complex patterns
            if matchList(pattern_list, pos, buf):
                print("offset: %d(0x%x)" % (actual_offset, actual_offset))

            # Move forward one byte to catch overlapping instances
            pos += 1
            
        if not chunk:
            # Reached end of file
            break
            
        # Keep the trailing edge of the current buffer to prepend to the next chunk
        # This handles patterns that cross the CHUNK_SIZE boundary.
        bytes_to_keep = buf[-overlap_size:] if overlap_size > 0 else bytearray()
        
        # Advance the absolute offset marker and reset buffer
        global_offset += len(buf) - len(bytes_to_keep)
        buf = bytearray(bytes_to_keep)
        
finally:
    if file_name != "":
        f.close()
