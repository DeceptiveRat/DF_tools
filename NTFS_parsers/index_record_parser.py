#!/bin/python3 

import sys
import getopt
import struct
import io
import subprocess
from dataclasses import dataclass
from mft_parser import FixupData
from mft_parser import readFixupData
from mft_parser import printFixupData
from mft_parser import prettyPrint
from mft_parser import revertFixupData

@dataclass 
class IndexRecordHeader:
	signature: int
	fixup_array_offset: int
	fixup_entry_count: int
	logfile_seq_num: int
	record_VCN: int

@dataclass 
class IndexNodeHeader:
	entry_start_offset: int
	entry_end_offset: int
	buffer_end_offset: int
	flags: int

@dataclass 
class IndexEntry:
	padding: bytes
	entry_len: int 
	content_len: int
	flags: int
	content: bytes
	padding2: bytes
	child_VCN: int

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("\t-h: display this help screen")
	print("\t-f <file>: file to parse. If this is not provided, stdin will be used")
	print("\t-r <int>: index record size. Default 4096 bytes")
	print("\t-i: ignore last entry in list flag. Useful for finding deleted entries")

def getBoundary(start_byte, boundary_size):
	if start_byte%boundary_size == 0:
		return start_byte
	else:
		return start_byte + (boundary_size - (start_byte%boundary_size))

def readIndexRecordHeader(byte_array):
	signature = int.from_bytes(byte_array[0:4])
	if signature != 0x494e4458:
		print("Warning! Signature doesn't match: %x" %(signature), file=sys.stderr)
	fixup_array_offset = int.from_bytes(byte_array[4:6], "little")
	fixup_entry_count = int.from_bytes(byte_array[6:8], "little")
	logfile_seq_num = int.from_bytes(byte_array[8:16], "little")
	record_VCN = int.from_bytes(byte_array[16:24], "little")

	return IndexRecordHeader(signature, fixup_array_offset, fixup_entry_count, \
		logfile_seq_num, record_VCN)

def printIndexRecordHeader(index_record_header):
	print("Index Record Header", "="*15)
	prettyPrint("Signature", index_record_header.signature, "hex")
	prettyPrint("Fixup array offset", index_record_header.fixup_array_offset, "int")
	prettyPrint("Fixup entry count", index_record_header.fixup_entry_count, "int")
	prettyPrint("$LogFile seq num", index_record_header.logfile_seq_num, "int")
	prettyPrint("Record VCN", index_record_header.record_VCN, "int")
	print("\n\n")

def readIndexNodeHeader(byte_array):
	entry_start_offset = int.from_bytes(byte_array[0:4], "little")
	entry_end_offset = int.from_bytes(byte_array[4:8], "little")
	buffer_end_offset = int.from_bytes(byte_array[8:12], "little")
	flags = int.from_bytes(byte_array[12:16], "little")

	return IndexNodeHeader(entry_start_offset, entry_end_offset, buffer_end_offset, \
		flags)

def printIndexNodeHeader(index_node_header):
	print("Index Node Header", "="*15)
	prettyPrint("Entry start offset", index_node_header.entry_start_offset, "int")
	prettyPrint("Entry end offset", index_node_header.entry_end_offset, "int")
	prettyPrint("List buffer end offset", index_node_header.buffer_end_offset, "int")
	prettyPrint("Flags", index_node_header.flags, "hex")
	if index_node_header.flags & 0x01:
		print("\t- Child node flag set")
	print("\n\n")

def readIndexEntry(byte_array):
	padding = byte_array[0:8]
	entry_len = int.from_bytes(byte_array[8:10], "little")
	content_len = int.from_bytes(byte_array[10:12], "little")
	flags = int.from_bytes(byte_array[12:16], "little")
	content = byte_array[16:16+content_len]
	boundary = getBoundary(16+content_len, 8)
	padding2 = byte_array[16+content_len:boundary]
	if flags&0x01:
		child_VCN = int.from_bytes(byte_array[boundary:boundary+8], "little")
		# not index entry 
		if boundary+8 != entry_len:
			return None, 8
			
		return IndexEntry(padding, entry_len, content_len, flags, content, \
			padding2, child_VCN), boundary+8
	
	if boundary != entry_len:
		return None, 8

	return IndexEntry(padding, entry_len, content_len, flags, content, \
		padding2, 0), boundary

def printIndexEntry(index_entry, deleted):
	if deleted:
		print("Delted ", end="")
	print("Index Entry", "="*15)
	print("First padding:")
	subprocess.run("xxd", input=index_entry.padding)
	prettyPrint("Entry length", index_entry.entry_len, "int")
	prettyPrint("Content length", index_entry.content_len, "int")
	prettyPrint("Flags", index_entry.flags, "hex")
	if index_entry.flags & 0x01:
		print("\t- Child node flag set")
	if index_entry.flags & 0x02:
		print("\t- Last entry flag set")
	print("Content:")
	subprocess.run("xxd", input=index_entry.content)
	prettyPrint("Child node VCN", index_entry.child_VCN, "int")
	print("Second padding:")
	subprocess.run("xxd", input=index_entry.padding2)
	print("\n\n")

def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "hf:r:i")
	except getopt.GetoptError as err:
		print(err)
		usage()
		sys.exit(-1)

	file_name=""
	ignore_last_entry_flag=False
	INDEX_RECORD_SIZE=4096
	INDEX_RECORD_HEADER_SIZE=24

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

	# read headers
	index_record_header = readIndexRecordHeader(data_bytes[0:24])
	printIndexRecordHeader(index_record_header)
	index_node_header = readIndexNodeHeader(data_bytes[24:40])
	printIndexNodeHeader(index_node_header)
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
	fixup_data = readFixupData(data_bytes[current_offset: \
		current_offset+fixup_data_length])
	printFixupData(fixup_data)
	current_offset+=fixup_data_length
	
	# fix slack values
	data_bytes = revertFixupData(data_bytes, fixup_data, INDEX_RECORD_SIZE)

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
		index_entry, bytes_read = readIndexEntry(data_bytes[current_offset:])

		# search for next entry
		if index_entry == None:
			print("Error: empty entry found before last entry", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)

		index_entry_list.append(index_entry)
		print("Index entry start offset: ", current_offset)
		current_offset += bytes_read
		printIndexEntry(index_entry, False)
		
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

		# last entry flag set
		if (index_entry.flags & 0x02):
			break

	# reached end without finding last entry flag
	if not(index_entry_list[-1].flags & 0x02):
		print("Warning: Could not find last entry flag", file=sys.stderr)
	
	# sanity check
	if not ignore_last_entry_flag:
		prettyPrint("end of buffer", 24+index_node_header.buffer_end_offset, "int")
		prettyPrint("end of read", current_offset, "int")
		sys.exit(1)

	# continue search for deleted entries
	while current_offset < INDEX_RECORD_SIZE - 16:
		bytes_read = 0
		index_entry, bytes_read = readIndexEntry(data_bytes[current_offset:])

		# search for next entry
		if index_entry == None:
			print("Searching for next entry...")
			prettyPrint("Current offset", current_offset, "int")
			current_offset+= bytes_read
			continue

		deleted_index_entry_list.append(index_entry)
		print("Index entry start offset: ", current_offset)
		current_offset += bytes_read
		printIndexEntry(index_entry, True)
		
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
	
	sys.exit(1)

if __name__ == "__main__": main()
