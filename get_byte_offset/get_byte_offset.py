#!/bin/python3 

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

def matchList(pattern_list, offset):
	for pattern_offset, pattern in pattern_list.items():
		start_offset = offset+pattern_offset
		end_offset = start_offset + len(pattern)
		if data_array[start_offset:end_offset] != pattern:
			return False
	
	return True

file_name = ""
max_search_length = 100000000 # 100,000,000
search_pattern=""
skip_length = 0
pattern_list={}

try:
	opts, args = getopt.getopt(sys.argv[1:], "hf:l:p:es:c:")
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
		search_pattern = bytes.fromhex(argument)
	elif option == "-s":
		skip_length = int(argument)
	elif option == "-c":
		for _ in argument.split(","):
			offset, pattern = _.split(":")
			pattern_list.update({int(offset):bytes.fromhex(pattern)})
	else:
		assert False, "unhandled option"

if search_pattern == "" and not pattern_list:
	print("Error! Please enter search pattern")
	exit(-1)

if file_name != "":
	with open(file_name, 'rb') as f:
		data_array = f.seek(skip_length)
		data_array = f.read()
else:
	data_array = sys.stdin.buffer.read(skip_length)
	data_array = sys.stdin.buffer.read()

if pattern_list:
	search_pattern = pattern_list[0]
	pattern_list.pop(0)

pos = 0
while True:
	# search for pattern
	pos=data_array.find(search_pattern, pos)
	if pos == -1:
		break
	
	# match remaining patterns
	if matchList(pattern_list, pos):
		# print offset
		print("offset: %d(0x%x)" %(skip_length + pos, skip_length+pos))

	# search starts from next byte
	pos+=1
