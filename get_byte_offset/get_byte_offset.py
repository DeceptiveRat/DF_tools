#!/bin/python3 

import sys
import io
import getopt

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("    -h: display this help screen")
	print("    -f <file>: file to search. If this is not provided, stdin is used")
	print("    -p <pattern>: [required] pattern to search for. Enter as hex; e.g. 3ccf10")
	print("    -s <int>: skip bytes")
	print("    -l <int>: max length to parse in bytes. Skipped bytes are included. Default: 100,000,000")

file_name = ""
chunk_length=1000000
max_search_length = 100000000
search_pattern=""
skip_length = 0

try:
	opts, args = getopt.getopt(sys.argv[1:], "hf:l:p:es:")
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
		search_length=int(argument)
	elif option == "-p":
		search_pattern = argument
	elif option == "-s":
		skip_length = int(argument)
	else:
		assert False, "unhandled option"

if search_pattern == "":
	print("Error! Please enter search pattern")
	exit(-1)

remaining_bytes = max_search_length - skip_length
read_length = chunk_length

# read only remaining bytes
if remaining_bytes < chunk_length:
	read_length = remaining_bytes

if file_name != "":
	with open(file_name, 'rb') as f:
		data_array = f.seek(skip_length)
		data_array = f.read(read_length)
else:
	data_array = sys.stdin.buffer.read(skip_length)
	data_array = sys.stdin.buffer.read(read_length)

remaining_bytes = remaining_bytes - read_length
offset = skip_length

while data_array != "":
	pos = 0
	while True:
		# search for pattern
		pos=data_array.find(bytes.fromhex(search_pattern), pos)
		if pos == -1:
			break
		# print offset
		print("offset: %d(0x%x)" %(offset+pos, offset+pos))
		# search starts from next byte
		pos+=1
	
	if remaining_bytes == 0:
		break
	
	offset = offset + read_length
	# read only remaining bytes
	if remaining_bytes < chunk_length:
		read_length =remaining_bytes

	if file_name != "":
		with open(file_name, 'rb') as f:
			data_array = f.seek(offset)
			data_array = f.read(read_length)
	else:
		data_array = sys.stdin.buffer.read(read_length)
	remaining_bytes = remaining_bytes - read_length
