#!/bin/python3 

import sys
import getopt
import struct
import io
from dataclasses import dataclass

# data classes
# =================================================
@dataclass 
class EntryHeader:
	signature: int
	fixup_array_offset: int
	fixup_entry_count: int
	logfile_seq_num: int
	seq_value: int
	link_count: int
	attr_offset: int
	flags: int
	entry_used_size: int
	entry_alloc_size: int
	base_record_file_ref: int
	next_attr_id: int
	padding: int
	entry_num: int

@dataclass 
class FixupData:
	padding: bytes
	padding_exist: int
	fixup_value: int
	original_value_array: list[int]

@dataclass 
class AttrHeader:
	attr_type_id: int
	attr_len: int
	non_resident_flag: int
	name_len: int
	name_offset: int
	flags: int
	attr_id: int

@dataclass 
class ResAttrHeader:
	attr_header: AttrHeader
	content_size: int
	content_offset: int

@dataclass 
class NonResAttrHeader:
	attr_header: AttrHeader
	runlist_start_VCN: int
	runlist_end_VCN: int
	runlist_offset: int
	compression_unit_size: int
	padding: int
	attr_content_alloc_size: int
	attr_content_actual_size: int
	attr_content_init_size: int

@dataclass 
class Runlist:
	run_length: int
	run_offset: int
	
# =================================================

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("-h: display this help screen")
	print("-f <file>: file to parse. File must contain raw bytes for mft entry. If this is not provided, stdin will be used")

def readEntryHeader(data_buffer) -> EntryHeader:
	signature = data_buffer.read(4)
	fixup_array_offset = int.from_bytes(data_buffer.read(2), "little")
	fixup_entry_count = int.from_bytes(data_buffer.read(2), "little")
	logfile_seq_num = int.from_bytes(data_buffer.read(8), "little")
	seq_value = int.from_bytes(data_buffer.read(2), "little")
	link_count = int.from_bytes(data_buffer.read(2), "little")
	attr_offset = int.from_bytes(data_buffer.read(2), "little")
	flags = int.from_bytes(data_buffer.read(2), "little")
	entry_used_size = int.from_bytes(data_buffer.read(4), "little")
	entry_alloc_size = int.from_bytes(data_buffer.read(4), "little")
	base_record_file_ref = int.from_bytes(data_buffer.read(8), "little")
	next_attr_id = int.from_bytes(data_buffer.read(2), "little")
	padding = data_buffer.read(2)
	entry_num = int.from_bytes(data_buffer.read(4), "little")
	return EntryHeader(signature, fixup_array_offset, fixup_entry_count, logfile_seq_num, seq_value, \
		link_count, attr_offset, flags, entry_used_size, entry_alloc_size, base_record_file_ref, next_attr_id, \
		padding, entry_num), 48

def printEntryHeader(entry_header):
	print("Entry Header", "="*100)
	if entry_header.signature != b'FILE':
		print("Signature not FILE", file=sys.stderr)
	else:
		print("Signature: FILE")
	print("offset to fixup array: %d" %(entry_header.fixup_array_offset))
	print("fixup array entry count: %d" %(entry_header.fixup_entry_count))
	print("$LogFile sequence number: %d" %(entry_header.logfile_seq_num))
	print("sequence value: %d" %(entry_header.seq_value))
	print("link count: %d" %(entry_header.link_count))
	print("attribute offset: %d" %(entry_header.attr_offset))
	if entry_header.flags & 0x01:
		print("flags: in use flag set")
	if entry_header.flags & 0x02:
		print("flags: directory flag set")
	print("MFT entry used size: %d" %(entry_header.entry_used_size))
	print("MFT entry allocated size: %d" %(entry_header.entry_alloc_size))
	print("file reference to base record: %d" %(entry_header.base_record_file_ref))
	print("next attribute id: %d" %(entry_header.next_attr_id))
	print("="*100, "\n\n\n")

def readFixupData(data_buffer, entry_header, offset) -> FixupData:
	padding = 0
	padding_exist = 0
	read_bytes = 0
	if offset < entry_header.fixup_array_offset:
		print("Warning: bytes before fixup value detected", file=sys.stderr)
		padding_exist = 1
		read_bytes = entry_header.fixup_array_offset - offset
		padding = data_buffer.read(read_bytes)
		print(padding.hex(), file=sys.stderr)
	elif offset > entry_header.fixup_array_offset:
		print("Warning: fixup array offset smaller than header size", file=sys.stderr)
		print("Terminating...", file=sys.stderr)
		sys.exit(-1)

	fixup_value = data_buffer.read(2)
	read_bytes += 2
	original_value_array = []
	for _ in range(entry_header.fixup_entry_count):
		original_value_array.append(data_buffer.read(2))
		read_bytes += 2
	
	return FixupData(padding, padding_exist, fixup_value, original_value_array), read_bytes

def printFixupData(fixup_data):
	print("Fixup data", "="*100)
	print("fixup value: 0x%s" %(fixup_data.fixup_value.hex()))
	print("original value list: ")
	for _ in range(len(fixup_data.original_value_array)):
		print("\t- 0x%s" %(fixup_data.original_value_array[_].hex()))
	print("="*100, "\n\n\n")

def readAttrHeader(data_buffer) -> AttrHeader:
	attr_type_id = int.from_bytes(data_buffer.read(4), "little")
	# reached end of entry
	if attr_type_id == 0xffffffff:
		sys.exit(2)
	attr_len = int.from_bytes(data_buffer.read(4), "little")
	non_resident_flag = int.from_bytes(data_buffer.read(1), "little")
	name_len = int.from_bytes(data_buffer.read(1), "little")
	name_offset = int.from_bytes(data_buffer.read(2), "little")
	flags = int.from_bytes(data_buffer.read(2), "little")
	attr_id = int.from_bytes(data_buffer.read(2), "little")
	return AttrHeader(attr_type_id, attr_len, non_resident_flag, name_len, \
		name_offset, flags, attr_id), 16

def printAttrType(attr_type_id):
	match attr_type_id:
		case 16:
			print(" ($STANDARD_INFORMATION)", end="")
		case 32:
			print(" ($ATTRIBUTE_LIST)", end="")
		case 48:
			print(" ($FILE_NAME)", end="")
		case 64:
			print(" ($OBJECT_ID)", end="")
		case 80:
			print(" ($SECURITY_DESCRIPTOR)", end="")
		case 96:
			print(" ($VOLUME_NAME)", end="")
		case 112:
			print(" ($VOLUME_INFORMATION)", end="")
		case 128:
			print(" ($DATA)", end="")
		case 144:
			print(" ($INDEX_ROOT)", end="")
		case 160:
			print(" ($INDEX_ALLOCATION)", end="")
		case 176:
			print(" ($BITMAP)", end="")
		case 192:
			print(" ($REPARSE_POINT)", end="")
		case 208:
			print(" ($EA_INFORMATION)", end="")
		case 224:
			print(" ($EA)", end="")
		case 256:
			print(" ($LOGGED_UTILITY_STREAM)", end="")
	
	print()
	return

def printAttrHeader(attr_header):
	print("attribute type id: %d" %(attr_header.attr_type_id), end="")
	printAttrType(attr_header.attr_type_id)
	print("attribute length: %d" %(attr_header.attr_len))
	if attr_header.non_resident_flag == 1:
		print("non-resident flag set")
	else:
		print("non-resident flag not set")
	print("name length: %d" %(attr_header.name_len))
	print("name offset: %d" %(attr_header.name_offset))
	print("flags set:")
	if attr_header.flags & 0x01: 
		print("\t- compressed flag set")
	if attr_header.flags & 0x4000:
		print("\t- encrypted flag set")
	if attr_header.flags & 0x8000:
		print("\t- sparse flag set")
	print("attribute id: %d" %(attr_header.attr_id))

def readResAttrHeader(data_buffer) -> ResAttrHeader:
	content_size = int.from_bytes(data_buffer.read(4), "little")
	content_offset = int.from_bytes(data_buffer.read(2), "little")
	return ResAttrHeader(None, content_size, content_offset), 6

def printResAttrHeader(res_attr_header):
	printAttrHeader(res_attr_header.attr_header)
	print("content size: %d" %(res_attr_header.content_size))
	print("content offset: %d" %(res_attr_header.content_offset))

def readNonResAttrHeader(data_buffer) -> NonResAttrHeader:
	runlist_start_VCN = int.from_bytes(data_buffer.read(8), "little")
	runlist_end_VCN = int.from_bytes(data_buffer.read(8), "little")
	runlist_offset = int.from_bytes(data_buffer.read(2), "little")
	compression_unit_size = int.from_bytes(data_buffer.read(2), "little")
	padding = int.from_bytes(data_buffer.read(4), "little")
	attr_content_alloc_size = int.from_bytes(data_buffer.read(8), "little")
	attr_content_actual_size = int.from_bytes(data_buffer.read(8), "little")
	attr_content_init_size = int.from_bytes(data_buffer.read(8), "little")
	return NonResAttrHeader(None, runlist_start_VCN, runlist_end_VCN, \
	runlist_offset, compression_unit_size, padding, attr_content_alloc_size, \
	attr_content_actual_size, attr_content_init_size), 48

def printNonResAttrHeader(nonres_attr_header):
	printAttrHeader(nonres_attr_header.attr_header)
	print("runlist starting VCN: %d" %(nonres_attr_header.runlist_start_VCN))
	print("runlist end VCN: %d" %(nonres_attr_header.runlist_end_VCN))
	print("runlist offset: %d" %(nonres_attr_header.runlist_offset))
	print("compression unit size: %d" %(nonres_attr_header.compression_unit_size))
	print("attribute content allocated size: %d" %(nonres_attr_header.attr_content_alloc_size))
	print("attribute content actual size: %d" %(nonres_attr_header.attr_content_actual_size))
	print("attribute content initialized size: %d" %(nonres_attr_header.attr_content_init_size))

def readRunlist(data_buffer):
	read_bytes=0
	runlist=[]
	length_byte = int.from_bytes(data_buffer.read(1))
	read_bytes += 1

	while length_byte != 0:
		run_offset_length = length_byte>>4
		run_length_length = length_byte & 0xf
		run_length = int.from_bytes(data_buffer.read(run_length_length), "little")
		read_bytes += run_length_length
		run_offset = int.from_bytes(data_buffer.read(run_offset_length), "little")
		# offset is negative
		if not (run_offset & 0x80):
			run_offset -= 0x10000
		read_bytes += run_offset_length
		length_byte = int.from_bytes(data_buffer.read(1))
		read_bytes += 1
		runlist.append(Runlist(run_length, run_offset))

	return runlist, read_bytes

def readAttr(data_buffer, current_offset):
	total_read_bytes = 0
	read_bytes = 0
	padding = b''
	attr_header = None
	res_attr_header =None
	nonres_attr_header = None
	attr_content = b''
	attr_runlist = []
	# read common attribute header
	attr_header, read_bytes = readAttrHeader(data_buffer)
	total_read_bytes += read_bytes

	# read rest of attribute header
	if attr_header.non_resident_flag == 0:
		res_attr_header, read_bytes = readResAttrHeader(data_buffer)
		res_attr_header.attr_header = attr_header
	elif attr_header.non_resident_flag == 1:
		nonres_attr_header, read_bytes = readNonResAttrHeader(data_buffer)
		nonres_attr_header.attr_header = attr_header
	else:
		print("Warning: corrupted non resident flag in attribute header", file=sys.stderr)
		sys.exit(-1)
	total_read_bytes += read_bytes
	
	# read attribute content
	if res_attr_header:
		# undefined bytes between header and content
		if total_read_bytes < res_attr_header.content_offset:
			print("Warning: bytes before content detected", file=sys.stderr)
			read_bytes = res_attr_header.content_offset - total_read_bytes
			padding = data_buffer.read(read_bytes)
			print(padding.hex(), file=sys.stderr)
			total_read_bytes += read_bytes
		elif total_read_bytes > res_attr_header.content_offset:
			print("Warning: corrupted content offset", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)
		# read contents
		attr_content = data_buffer.read(res_attr_header.content_size)
		total_read_bytes += res_attr_header.content_size
	else:
		# undefined bytes between header and content
		if total_read_bytes < nonres_attr_header.runlist_offset:
			print("Warning: bytes before content detected", file=sys.stderr)
			read_bytes = nonres_attr_header.runlist_offset - total_read_bytes
			padding = data_buffer.read(read_bytes)
			total_read_bytes += read_bytes
			print(padding.hex(), file=sys.stderr)
		elif total_read_bytes > nonres_attr_header.runlist_offset:
			print("Warning: corrupted runlist offset", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)

		# read runlist 
		attr_runlist, read_bytes = readRunlist(data_buffer)
		total_read_bytes += read_bytes
			
	return res_attr_header, nonres_attr_header, attr_content, attr_runlist, total_read_bytes

def printResAttr(res_attr_header, attr_content):
	print("Resident Attribute", "="*100)
	printResAttrHeader(res_attr_header)
	print("Content:")
	# print content
	print("="*100, "\n\n\n")

def printNonResAttr(non_res_attr_header, attr_runlist):
	print("Non-resident Attribute", "="*100)
	printNonResAttrHeader(non_res_attr_header)
	cumulated_offset = 0
	for _ in range(len(attr_runlist)):
		cumulated_offset += attr_runlist[_].run_offset
		print("\tRunlist[%d]:\tRun Length: %d\t\t\tRun Offset: %d(%d from start of FS)" %(_, attr_runlist[_].run_length, attr_runlist[_].run_offset, cumulated_offset))

	print("Content:")
	# print content

	print("="*100, "\n\n\n")
	
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

	data_array=b''

	if file_name != "":
		with open(file_name, 'rb') as f:
			data_array = f.read(1024)
	else:
		data_array = sys.stdin.buffer.read(1024)

	data_buffer = io.BytesIO(data_array)
	current_offset = 0
	read_bytes = 0
	padding_after_fixup = b''
	padding = b''
	entry_header = None
	fixup_data = None
	attr_list = []

	# parse MFT entry header
	entry_header, read_bytes = readEntryHeader(data_buffer)
	current_offset += read_bytes
	printEntryHeader(entry_header)

	# parse fixup value
	fixup_data, read_bytes = readFixupData(data_buffer, entry_header, current_offset)
	current_offset += read_bytes
	printFixupData(fixup_data)

	# replace fixup signature values with original values
	corrected_data_array=bytearray(data_array)
	if data_array[510:512] != fixup_data.fixup_value:
		print("Warning: value at end of sector 1 does not match fixup signature", file=sys.stderr)
		print("Signature value: %s\t\t\tValue at end of sector: %s" %(fixup_data.fixup_value.hex(), data_array[510:512].hex()), file=sys.stderr)
	corrected_data_array[510:512] = fixup_data.original_value_array[0]

	if data_array[1022:1024] != fixup_data.fixup_value:
		print("Warning: value at end of sector 2 does not match fixup signature", file=sys.stderr)
		print("Signature value: %s\t\t\tValue at end of sector: %s" %(fixup_data.fixup_value.hex(), data_array[1022:1024].hex()), file=sys.stderr)
	corrected_data_array[1022:1024] = fixup_data.original_value_array[1]

	# read data array again
	data_buffer = io.BytesIO(bytes(corrected_data_array))
	data_buffer.seek(current_offset)
	
	if current_offset < entry_header.attr_offset:
		print("Warning: bytes before first attribute detected", file=sys.stderr)
		read_bytes = entry_header.attr_offset - current_offset
		padding_after_fixup = data_buffer.read(read_bytes)
		current_offset += read_bytes
		print(padding_after_fixup.hex(), file=sys.stderr)
	elif current_offset > entry_header.attr_offset:
		print("Warning: first attribute offset smaller than current offset", file=sys.stderr)
		print("Terminating...", file=sys.stderr)
		sys.exit(-1)

	# parse attributes
	while current_offset != entry_header.entry_used_size:
		res_atr_header = None
		nonres_attr_header = None
		attr_content = b''
		attr_runlist = []
		
		res_attr_header, nonres_attr_header, attr_content, attr_runlist, read_bytes = readAttr(data_buffer, current_offset)
		current_offset += read_bytes
		if res_attr_header:
			current_attr_length = res_attr_header.attr_header.attr_len
		else:
			current_attr_length = nonres_attr_header.attr_header.attr_len

		# too little bytes read
		if read_bytes < current_attr_length:
			print("Warning: bytes after attribute detected", file=sys.stderr)
			read_bytes = current_attr_length - read_bytes
			padding = data_buffer.read(read_bytes)
			current_offset += read_bytes
			print(padding.hex(), file=sys.stderr)
		# too many bytes read
		elif read_bytes > current_attr_length:
			print("Warning: attribute length value corrupted", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)
		
		# print and save attr
		if res_attr_header: 
			printResAttr(res_attr_header, attr_content)
			attr_list.append([res_attr_header, attr_content])
		else:
			printNonResAttr(nonres_attr_header, attr_runlist)
			attr_list.append([nonres_attr_header, attr_runlist])

if __name__ == "__main__": main()
