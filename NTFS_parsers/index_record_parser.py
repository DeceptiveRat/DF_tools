#!/bin/python3 

import sys
import getopt
import struct
import io
import subprocess
from dataclasses import dataclass

import index_record as ir
import fixup_data as fd
import pretty_print as pp
from get_boundary import getBoundary

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("\t-h: display this help screen")
	print("\t-f <file>: file to parse. If this is not provided, stdin will be used")
	print("\t-r <int>: index record size. Default 4096 bytes")
	print("\t-i: ignore last entry in list flag. Useful for finding deleted entries")
	print("\t-d: index record contains directory contents; i.e. directory flag \
		set and attribute name $I30")
	print("\t-q: quiet mode. Only output extracted entry")
	print("\t-e <int>,<int>,<int>: entries to extract")
	print("\t-r: used with -e. Extract raw bytes to file raw.dat")

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hf:r:ide:qr")
	except getopt.GetoptError as err:
		print(err)
		usage()
		sys.exit(-1)

	file_name=""
	ignore_last_entry_flag=False
	INDEX_RECORD_SIZE=4096
	INDEX_RECORD_HEADER_SIZE=24
	is_directory=False
	extract_num_list = []
	quiet_mode = False
	raw_extract = False

	for option, argument in opts:
		if option == "-h":
			usage()
			sys.exit()
		elif option == "-f":
			file_name = argument 
		elif option == "-r":
			INDEX_RECORD_SIZE = int(argument)
		elif option == "-i":
			ignore_last_entry_flag = True
		elif option == "-d":
			is_directory = True
		elif option == "-e":
			for _ in argument.split(","):
				extract_num_list.append(int(_))
		elif option == "-r":
			raw_extract = True
		elif option == "-q":
			quiet_mode = True
		else:
			assert False, "unhandled option"

	data_bytes=b''

	if file_name != "":
		with open(file_name, 'rb') as f:
			data_bytes = f.read(INDEX_RECORD_SIZE)
	else:
		data_bytes = sys.stdin.buffer.read(INDEX_RECORD_SIZE)
	
	index_record_header = None
	index_node_header = None
	index_entry_list = []
	deleted_index_entry_list = []
	index_entry = None
	current_offset = 0
	index_entry_number = 0

	# read headers
	index_record_header = ir.readIndexRecordHeader(data_bytes[0:24])
	if not quiet_mode:
		ir.printIndexRecordHeader(index_record_header)
	index_node_header = ir.readIndexNodeHeader(data_bytes[24:40])
	if not quiet_mode:
		ir.printIndexNodeHeader(index_node_header)
	current_offset = 40

	# slack check
	if index_record_header.fixup_array_offset > current_offset:
		read_bytes = index_record_header.fixup_array_offset - current_offset
		print("Warning: bytes before fixup data detected", file=sys.stderr)
		print("Extra bytes:\n", data_bytes[current_offset: \
			current_offset+read_bytes], file=sys.stderr)
		current_offset += read_bytes
	elif index_record_header.fixup_array_offset < current_offset:
		print("Warning: fixup array offset value corrupted", file=sys.stderr)
		print("Terminating...", file=sys.stderr)
		sys.exit(-1)

	# read fixup data
	fixup_data_length = 2+index_record_header.fixup_entry_count*2
	fixup_data = fd.readFixupData(data_bytes[current_offset: \
		current_offset+fixup_data_length])
	if not quiet_mode:
		fd.printFixupData(fixup_data)
	current_offset+=fixup_data_length
	
	# fix slack values
	data_bytes = fd.revertFixupData(data_bytes, fixup_data, INDEX_RECORD_SIZE)

	# slack check
	if 24 + index_node_header.entry_start_offset > current_offset:
		read_bytes = 24 + index_node_header.entry_start_offset - current_offset
		print("Warning: bytes before index entry detected", file=sys.stderr)
		print("Extra bytes:\n", data_bytes[current_offset: \
			current_offset+read_bytes], file=sys.stderr)
		current_offset += read_bytes
	elif 24 + index_record_header.fixup_array_offset < current_offset:
		print("Warning: index entry offset value corrupted", file=sys.stderr)
		print("Terminating...", file=sys.stderr)
		sys.exit(-1)

	while current_offset < INDEX_RECORD_SIZE - 16:
		bytes_read = 0
		index_entry, bytes_read = ir.readIndexEntry(data_bytes[current_offset:])

		# search for next entry
		if index_entry == None:
			print("Error: empty entry found before last entry", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)

		if is_directory:
			index_entry = ir.DirectoryIndexEntry( \
				int.from_bytes(index_entry.padding, "little"), \
				index_entry.entry_len, index_entry.content_len, \
				index_entry.flags, index_entry.content, index_entry.padding2, \
				index_entry.child_VCN)

		index_entry_list.append(index_entry)
		index_entry_number+=1
		if not quiet_mode:
			print("Index entry[%d] start offset: %d" %(index_entry_number, current_offset))
			ir.printIndexEntry(index_entry, False, is_directory)
		current_offset += bytes_read
		
		# length sanity check
		if bytes_read < index_entry.entry_len:
			print("Warning: index entry length(%d) doesn't match bytes read(%d)" \
				%(index_entry.entry_len, bytes_read), file=sys.stderr)
			print("Extra bytes:\n", data_bytes[current_offset+bytes_read: \
				current_offset+index_entry.entry_len], file=sys.stderr)
		elif bytes_read > index_entry.entry_len:
			print("Warning: index entry length(%d) doesn't match bytes read(%d)" \
				%(index_entry.entry_len, bytes_read), file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)

		if index_entry_number in extract_num_list:
			if raw_extract:
				with open("raw.dat", "ab") as f:
					f.write(data_bytes[prev_offset:current_offset])
			else:
				print("Entry %d at offset %d" %(index_entry_number, prev_offset))
				subprocess.run("xxd", input=data_bytes[prev_offset:current_offset])
				ir.printIndexEntry(index_entry, False, is_directory)

		prev_offset = current_offset

		# last entry flag set
		if (index_entry.flags & 0x02):
			break

	# reached end without finding last entry flag
	if not(index_entry_list[-1].flags & 0x02):
		print("Warning: Could not find last entry flag", file=sys.stderr)
	
	# sanity check
	if not ignore_last_entry_flag:
		if not quiet_mode:
			pp.prettyPrint("end of buffer", 24+index_node_header.buffer_end_offset, "int")
			pp.prettyPrint("end of read", current_offset, "int")
		sys.exit(1)

	# continue search for deleted entries
	while current_offset < INDEX_RECORD_SIZE - 16:
		bytes_read = 0
		index_entry, bytes_read = ir.readIndexEntry(data_bytes[current_offset:])

		# search for next entry
		if index_entry == None:
			if not quiet_mode:
				print("Searching for next entry...")
				pp.prettyPrint("Current offset", current_offset, "int")
			current_offset+= bytes_read
			continue

		if is_directory:
			index_entry = ir.DirectoryIndexEntry( \
				int.from_bytes(index_entry.padding, "little"), \
				index_entry.entry_len, index_entry.content_len, \
				index_entry.flags, index_entry.content, index_entry.padding2, \
				index_entry.child_VCN)

		deleted_index_entry_list.append(index_entry)
		index_entry_number+=1
		if not quiet_mode:
			print("Index entry[%d] start offset: %d" %(index_entry_number, current_offset))
			ir.printIndexEntry(index_entry, True, is_directory)
		current_offset += bytes_read
		
		# length sanity check
		if bytes_read < index_entry.entry_len:
			print("Warning: index entry length(%d) doesn't match bytes read(%d)" \
				%(index_entry.entry_len, bytes_read), file=sys.stderr)
			print("Extra bytes:\n", data_bytes[current_offset+bytes_read: \
				current_offset+index_entry.entry_len], file=sys.stderr)
		elif bytes_read > index_entry.entry_len:
			print("Warning: index entry length(%d) doesn't match bytes read(%d)" \
				%(index_entry.entry_len, bytes_read), file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)

		if index_entry_number in extract_num_list:
			if raw_extract:
				with open("raw.dat", "ab") as f:
					f.write(data_bytes[prev_offset:current_offset])
			else:
				print("Entry %d at offset %d" %(index_entry_number, prev_offset))
				subprocess.run("xxd", input=data_bytes[prev_offset:current_offset])
				ir.printIndexEntry(index_entry, True, is_directory)

		prev_offset = current_offset
	
	sys.exit(1)

if __name__ == "__main__": main()
