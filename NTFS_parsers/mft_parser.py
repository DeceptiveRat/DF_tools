#!/bin/python3 

import sys
import getopt
import struct
import io
from dataclasses import dataclass

import fixup_data as fd
import mft_entry as me
import pretty_print as pp

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("-h: display this help screen")
	print("-f <file>: file to parse. File must contain raw bytes for mft entry. \
		If this is not provided, stdin will be used")
	
def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hf:")
	except getopt.GetoptError as err:
		print(err)
		usage()
		sys.exit(-1)

	file_name=""

	for option, argument in opts:
		if option == "-h":
			usage()
			sys.exit()
		elif option == "-f":
			file_name = argument 
		else:
			assert False, "unhandled option"

	data_bytes=b''
	MFT_ENTRY_LENGTH=1024

	if file_name != "":
		with open(file_name, 'rb') as f:
			data_bytes = f.read(MFT_ENTRY_LENGTH)
	else:
		data_bytes = sys.stdin.buffer.read(MFT_ENTRY_LENGTH)

	current_offset = 0
	read_bytes = 0
	padding_after_fixup = b''
	padding = b''
	entry_header = None
	fixup_data = None
	attr_list = []

	# parse MFT entry header
	entry_header = me.readEntryHeader(data_bytes[0:48])
	current_offset += 48
	me.printEntryHeader(entry_header)

	# parse fixup value
	if current_offset < entry_header.fixup_array_offset:
		print("Warning: bytes before fixup value detected", file=sys.stderr)
		print("Extra bytes:\n", data_bytes[current_offset: \
			entry_header.fixup_array_offset], file=sys.stderr)
		current_offset = entry_header.fixup_array_offset
	elif current_offset > entry_header.fixup_array_offset:
		print("Warning: fixup array offset smaller than header size", file=sys.stderr)
		print("Terminating...", file=sys.stderr)
		sys.exit(-1)
	fixup_data_length = 2+entry_header.fixup_entry_count*2
	fixup_data = fd.readFixupData(data_bytes[current_offset: \
		current_offset+fixup_data_length])
	current_offset += fixup_data_length
	fd.printFixupData(fixup_data)

	# replace fixup signature values with original values
	data_bytes = fd.revertFixupData(data_bytes, fixup_data, MFT_ENTRY_LENGTH)

	if current_offset < entry_header.attr_offset:
		print("Warning: bytes before first attribute detected", file=sys.stderr)
		print("Extra bytes:\n", data_bytes[current_offset: \
			entry_header.attr_offset], file=sys.stderr)
		current_offset = entry_header.attr_offset
	elif current_offset > entry_header.attr_offset:
		print("Warning: first attribute offset smaller than current offset", \
			file=sys.stderr)
		print("Terminating...", file=sys.stderr)
		sys.exit(-1)

	# parse attributes
	while current_offset != entry_header.entry_used_size:
		res_attr_header = None
		nonres_attr_header = None
		attr_content = b''
		attr_runlist = []
		
		res_attr_header, nonres_attr_header, attr_content, attr_runlist, read_bytes \
			= me.readAttr(data_bytes[current_offset:])
		if res_attr_header:
			current_attr_length = res_attr_header.attr_header.attr_len
		else:
			current_attr_length = nonres_attr_header.attr_header.attr_len

		# too few bytes read
		if read_bytes < current_attr_length:
			print("Warning: bytes after attribute detected", file=sys.stderr)
			print("Extra bytes:\n", data_bytes[current_offset+read_bytes: \
				current_offset+current_attr_length], file=sys.stderr)
		# too many bytes read
		elif read_bytes > current_attr_length:
			print("Warning: attribute length value corrupted", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)
		current_offset += current_attr_length
		
		# print and save attr
		if res_attr_header: 
			me.printResAttr(res_attr_header, attr_content)
			attr_list.append([res_attr_header, attr_content])
		else:
			me.printNonResAttr(nonres_attr_header, attr_runlist)
			attr_list.append([nonres_attr_header, attr_runlist])

if __name__ == "__main__": main()
