#!/bin/python3 

import sys
import getopt
import struct
import io
from dataclasses import dataclass
from mft_parser import readFixupData
from mft_parser import printFixupData

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
	print("%-31s 0x%x" %("Signature:", index_record_header.signature))
	print("%-31s %d" %("Fixup array offset:", index_record_header.fixup_array_offset))
	print("%-31s %d" %("Fixup entry count:", index_record_header.fixup_entry_count))
	print("%-31s %d" %("$LogFile seq num:", index_record_header.logfile_seq_num))
	print("%-31s %d" %("Record VCN:", index_record_header.record_VCN))

def readIndexNodeHeader(byte_array):
	entry_start_offset = int.from_bytes(byte_array[0:4], "little")
	entry_end_offset = int.from_bytes(byte_array[4:8], "little")
	buffer_end_offset = int.from_bytes(byte_array[8:12], "little")
	flags = int.from_bytes(byte_array[12:16], "little")

	return IndexNodeHeader(entry_start_offset, entry_end_offset, buffer_end_offset, \
		flags)

def printIndexNodeHeader(index_node_header):
	print("%-31s %d" %("Entry start offset", index_node_header.entry_start_offset))
	print("%-31s %d" %("Entry end offset", index_node_header.entry_end_offset))
	print("%-31s %d" %("List buffer end offset", index_node_header.buffer_end_offset))
	print("%-31s 0x%x:" %("Flags:", index_node_header.flags))
	if index_node_header.flags & 0x01:
		print("\t- Child node flag set")

def readIndexEntry(byte_array):
	entry_len = int.from_bytes(byte_array[8:10], "little")
	# search for start of next entry; used when looking for deleted entries
	if entry_len == 0:
		return None, 2
	padding = int.from_bytes(byte_array[0:8])
	content_len = int.from_bytes(byte_array[10:12], "little")
	flags = int.from_bytes(byte_array[12:16], "little")
	content = byte_array[16:16+content_len]
	boundary = getBoundary(16+content_len, 8)
	padding2 = byte_array[16+content_len:boundary]
	child_VCN = int.from_bytes(byte_array[boundary:boundary+8], "little")
	
	return IndexEntry(padding, entry_len, content_len, flags, content, \
		padding2, child_VCN), boundary+8

def printIndexEntry(index_entry):
	print("First padding:\n", index_entry.padding)
	print("%-31s %d" %("Entry length", index_entry.entry_len))
	print("%-31s %d" %("Content length", index_entry.content_len))
	print("%-31s 0x%x:" %("Flags:", index_entry.flags))
	if index_entry.flags & 0x01:
		print("\t- Child node flag set")
	if index_entry.flags & 0x02:
		print("\t- Last entry flag set")
	print("Content:\n", index_entry.content)
	print("%-31s %d" %("Child node VCN", index_entry.child_VCN))
	print("First padding:\n", index_entry.padding2)

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

	data_array=b''

	if file_name != "":
		with open(file_name, 'rb') as f:
			data_array = f.read(INDEX_RECORD_SIZE)
	else:
		data_array = sys.stdin.buffer.read(INDEX_RECORD_SIZE)
	
	index_record_header = None
	index_node_header = None
	index_entry_list = []
	index_entry = None
	current_offset = 0

	# read headers
	index_record_header = readIndexRecordHeader(data_array[0:24])
	printIndexRecordHeader(index_record_header)
	index_node_header = readIndexNodeHeader(data_array[24:40])

	# read fixup data
	

	current_offset = 40
	while True:
		bytes_read = 0
		index_entry, bytes_read = readIndexEntry(data_array[current_offset:])

		# search for next entry
		if index_entry == None:
			current_offset+= bytes_read
			continue
		
		# length sanity check
		if bytes_read < index_entry.entry_len:
			print("Warning: index entry length(%d) doesn't match bytes read(%d)" \
				%(index_entry.entry_len, bytes_read), file=sys.stderr)
			print("Extra bytes:\n", data_array[current_offset+bytes_read: \
				current_offset+index_entry.entry_len], file=sys.stderr)
		elif bytes_read > index_entry.entry_len:
			print("Warning: index entry length(%d) doesn't match bytes read(%d)" \
				%(index_entry.entry_len, bytes_read), file=sys.stderr)
			print("terminating...")
			sys.exit(-1)

		current_offset += bytes_read
		index_entry_list.append(index_entry)
		# last entry flag set
		if (index_entry.flags & 0x02) & (not ignore_last_entry_flag):
			break
		# max size reached
		if current_offset >= INDEX_RECORD_SIZE - 24:
			break
	
	# sanity check
	if not ignore_last_entry_flag:
		print("%-31s: %d" %("end of buffer", \
			24+index_node_header.buffer_end_offset))
		print("%-31s: %d" %("end of read", current_offset))

if __name__ == "__main__": main()
