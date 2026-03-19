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
	padding: bytes
	entry_num: int

@dataclass 
class FixupData:
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
	padding: bytes
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
	print("-f <file>: file to parse. File must contain raw bytes for mft entry. \
		If this is not provided, stdin will be used")

def prettyPrint(field, value, data_type):
	if data_type == "int":
		print("%-20s: %d" %(field, value))
	elif data_type == "hex":
		print("%-20s: 0x%x" %(field, value))
	elif data_type == "bytes":
		print("%-20s:\n" %(field))
		print(value)
	elif data_type == "string":
		print("%-20s: %s" %(field, value))

def readEntryHeader(data_bytes) -> EntryHeader:
	signature = data_bytes[0:4]
	fixup_array_offset = int.from_bytes(data_bytes[4:6], "little")
	fixup_entry_count = int.from_bytes(data_bytes[6:8], "little")
	logfile_seq_num = int.from_bytes(data_bytes[8:16], "little")
	seq_value = int.from_bytes(data_bytes[16:18], "little")
	link_count = int.from_bytes(data_bytes[18:20], "little")
	attr_offset = int.from_bytes(data_bytes[20:22], "little")
	flags = int.from_bytes(data_bytes[22:24], "little")
	entry_used_size = int.from_bytes(data_bytes[24:28], "little")
	entry_alloc_size = int.from_bytes(data_bytes[28:32], "little")
	base_record_file_ref = int.from_bytes(data_bytes[32:40], "little")
	next_attr_id = int.from_bytes(data_bytes[40:42], "little")
	padding = data_bytes[42:44]
	entry_num = int.from_bytes(data_bytes[44:48], "little")
	return EntryHeader(signature, fixup_array_offset, fixup_entry_count, \
		logfile_seq_num, seq_value, link_count, attr_offset, flags, \
		entry_used_size, entry_alloc_size, base_record_file_ref, next_attr_id, \
		padding, entry_num)

def printEntryHeader(entry_header):
	print("Entry Header", "="*15)
	if entry_header.signature != b'FILE':
		print("Signature not FILE", file=sys.stderr)
	else:
		print("Signature: FILE")
	prettyPrint("fixup array offset", entry_header.fixup_array_offset, "int")
	prettyPrint("fixup entry count", entry_header.fixup_entry_count, "int")
	prettyPrint("$LogFile seq num", entry_header.logfile_seq_num, "int")
	prettyPrint("sequence value", entry_header.seq_value, "int")
	prettyPrint("link count", entry_header.link_count, "int")
	prettyPrint("attribute offset", entry_header.attr_offset, "int")
	if entry_header.flags & 0x01:
		print("flags: in use flag set")
	if entry_header.flags & 0x02:
		print("flags: directory flag set")
	prettyPrint("MFT entry used size", entry_header.entry_used_size, "int")
	prettyPrint("MFT entry allocated size", entry_header.entry_alloc_size, "int")
	prettyPrint("file reference to base record", entry_header.base_record_file_ref \
		, "int")
	prettyPrint("next attribute id", entry_header.next_attr_id, "int")
	print("\n\n")

def readFixupData(data_bytes) -> FixupData:
	offset = 0
	fixup_value = data_bytes[0:2]
	offset = 2
	original_value_array = []
	while offset != len(data_bytes):
		original_value_array.append(data_bytes[offset:offset+2])
		offset+=2
	
	return FixupData(fixup_value, original_value_array)

def printFixupData(fixup_data):
	print("Fixup data", "="*15)
	prettyPrint("fixup value:", int.from_bytes(fixup_data.fixup_value), "hex")
	print("original value list: ")
	for _ in range(len(fixup_data.original_value_array)):
		print("\t- 0x%s" %(fixup_data.original_value_array[_].hex()))
	print("\n\n")

def revertFixupData(data_bytes, fixup_data, data_length):
	fixed_data_bytes = bytearray(data_bytes)
	for offset in range(510, data_length, 512):
		# doesn't match
		if data_bytes[offset:offset+2] != fixup_data.fixup_value:
			print("Warning: value at end of sector %d does not match \
				fixup signature" %((offset/512)+1), file=sys.stderr)
			print("Signature value: 0x%s\tValue at end of sector %d: 0x%s" \
				%((offset/512)+1), fixup_data.fixup_value.hex(), \
				data_bytes[offset:offset+2].hex(), file=sys.stderr)

		# fix value
		fixed_data_bytes[offset:offset+2] = fixup_data.original_value_array[0]

	return bytes(fixed_data_bytes)
	

def readAttrHeader(data_bytes) -> AttrHeader:
	attr_type_id = int.from_bytes(data_bytes[0:4], "little")
	# reached end of entry
	if attr_type_id == 0xffffffff:
		sys.exit(2)
	attr_len = int.from_bytes(data_bytes[4:8], "little")
	non_resident_flag = int.from_bytes(data_bytes[8:9], "little")
	name_len = int.from_bytes(data_bytes[9:10], "little")
	name_offset = int.from_bytes(data_bytes[10:12], "little")
	flags = int.from_bytes(data_bytes[12:14], "little")
	attr_id = int.from_bytes(data_bytes[14:16], "little")
	return AttrHeader(attr_type_id, attr_len, non_resident_flag, name_len, \
		name_offset, flags, attr_id)

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
	prettyPrint("attribute length", attr_header.attr_len, "int")
	if attr_header.non_resident_flag == 1:
		prettyPrint("non resident flag", "non-resident flag set", "string")
	else:
		prettyPrint("non resident flag", "non-resident flag not set", "string")
	prettyPrint("name length", attr_header.name_len, "int")
	prettyPrint("name offset", attr_header.name_offset, "int")
	print("flags set:")
	if attr_header.flags & 0x01: 
		print("\t- compressed flag set")
	if attr_header.flags & 0x4000:
		print("\t- encrypted flag set")
	if attr_header.flags & 0x8000:
		print("\t- sparse flag set")
	prettyPrint("attribute id", attr_header.attr_id, "int")

def readResAttrHeader(data_bytes) -> ResAttrHeader:
	content_size = int.from_bytes(data_bytes[0:4], "little")
	content_offset = int.from_bytes(data_bytes[4:6], "little")
	return ResAttrHeader(None, content_size, content_offset)

def printResAttrHeader(res_attr_header):
	printAttrHeader(res_attr_header.attr_header)
	prettyPrint("content size:", res_attr_header.content_size, "int")
	prettyPrint("content offset:", res_attr_header.content_offset, "int")

def readNonResAttrHeader(data_bytes) -> NonResAttrHeader:
	runlist_start_VCN = int.from_bytes(data_bytes[0:8], "little")
	runlist_end_VCN = int.from_bytes(data_bytes[8:16], "little")
	runlist_offset = int.from_bytes(data_bytes[16:18], "little")
	compression_unit_size = int.from_bytes(data_bytes[18:20], "little")
	padding = data_bytes[20:24]
	attr_content_alloc_size = int.from_bytes(data_bytes[24:32], "little")
	attr_content_actual_size = int.from_bytes(data_bytes[32:40], "little")
	attr_content_init_size = int.from_bytes(data_bytes[40:48], "little")
	return NonResAttrHeader(None, runlist_start_VCN, runlist_end_VCN, \
	runlist_offset, compression_unit_size, padding, attr_content_alloc_size, \
	attr_content_actual_size, attr_content_init_size)

def printNonResAttrHeader(nonres_attr_header):
	printAttrHeader(nonres_attr_header.attr_header)
	prettyPrint("runlist starting VCN", nonres_attr_header.runlist_start_VCN, "int")
	prettyPrint("runlist end VCN", nonres_attr_header.runlist_end_VCN, "int")
	prettyPrint("runlist offset", nonres_attr_header.runlist_offset, "int")
	prettyPrint("compression unit size", nonres_attr_header.compression_unit_size, \
		"int")
	prettyPrint("content allocated size", \
		nonres_attr_header.attr_content_alloc_size, "int")
	prettyPrint("content actual size", \
		nonres_attr_header.attr_content_actual_size, "int")
	prettyPrint("content initialized size", \
		nonres_attr_header.attr_content_init_size, "int")

def readRunlist(data_bytes):
	current_offset=0
	runlist=[]
	length_byte = int.from_bytes(data_bytes[current_offset:current_offset+1])
	current_offset += 1

	while length_byte != 0:
		run_offset_length = length_byte>>4
		run_length_length = length_byte & 0xf
		run_length = int.from_bytes(data_bytes[current_offset: \
			current_offset+run_length_length], "little")
		current_offset += run_length_length
		run_offset = int.from_bytes(data_bytes[current_offset: \
			current_offset+run_offset_length], "little")
		current_offset += run_offset_length
		# offset is negative
		if run_offset & 0x8000:
			run_offset -= 0x10000
		length_byte = int.from_bytes(data_bytes[current_offset:current_offset+1])
		current_offset += 1
		runlist.append(Runlist(run_length, run_offset))

	return runlist, current_offset

def readAttr(data_bytes):
	# TODO: parse attribute name
	current_offset = 0
	read_bytes = 0
	padding = b''
	attr_header = None
	res_attr_header =None
	nonres_attr_header = None
	attr_content = b''
	attr_runlist = []
	# read common attribute header
	attr_header = readAttrHeader(data_bytes[0:16])
	current_offset += 16

	# read rest of attribute header
	if attr_header.non_resident_flag == 0:
		res_attr_header = readResAttrHeader(data_bytes[16:22])
		res_attr_header.attr_header = attr_header
		current_offset += 6
	elif attr_header.non_resident_flag == 1:
		nonres_attr_header = readNonResAttrHeader(data_bytes[16:64])
		nonres_attr_header.attr_header = attr_header
		current_offset += 48
	else:
		print("Warning: corrupted non resident flag in attribute header" \
			, file=sys.stderr)
		sys.exit(-1)
	
	# read attribute content
	if res_attr_header:
		# undefined bytes between header and content
		if current_offset < res_attr_header.content_offset:
			print("Warning: bytes before content detected", file=sys.stderr)
			print("Extra bytes:\n", data_bytes[current_offset: \
				res_attr_header.content_offset], file=sys.stderr)
			current_offset = res_attr_header.content_offset
		elif current_offset > res_attr_header.content_offset:
			print("Warning: corrupted content offset", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)
		# read contents
		attr_content = data_bytes[current_offset: \
			current_offset + res_attr_header.content_size]
		current_offset += res_attr_header.content_size
	else:
		# undefined bytes between header and content
		if current_offset < nonres_attr_header.runlist_offset:
			print("Warning: bytes before content detected", file=sys.stderr)
			print("Extra bytes:\n", data_bytes[current_offset: \
				nonres_attr_header.runlist_offset], file=sys.stderr)
			current_offset = nonres_attr_header.runlist_offset
		elif current_offset > nonres_attr_header.runlist_offset:
			print("Warning: corrupted runlist offset", file=sys.stderr)
			print("Terminating...", file=sys.stderr)
			sys.exit(-1)

		# read runlist 
		attr_runlist, read_bytes = readRunlist(data_bytes[current_offset:])
		current_offset += read_bytes
			
	return res_attr_header, nonres_attr_header, attr_content, attr_runlist, \
		current_offset

def printResAttr(res_attr_header, attr_content):
	print("Resident Attribute", "="*15)
	printResAttrHeader(res_attr_header)

	print("Content:")
	# print content
	print(attr_content)
	print("\n\n")

def printNonResAttr(non_res_attr_header, attr_runlist):
	print("Non-resident Attribute", "="*15)
	printNonResAttrHeader(non_res_attr_header)
	cumulated_offset = 0
	for _ in range(len(attr_runlist)):
		cumulated_offset += attr_runlist[_].run_offset
		print("\tRunlist[%d]:\tRun Length: %d\t\t\tRun Offset: %d(%d from start of FS)" %(_, attr_runlist[_].run_length, attr_runlist[_].run_offset, cumulated_offset))

	print("Content:")
	# print content

	print("\n\n")
	
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
	MFT_ENTRY_LENGTH

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
	entry_header = readEntryHeader(data_bytes[0:48])
	current_offset += 48
	printEntryHeader(entry_header)

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
	fixup_data = readFixupData(data_bytes[current_offset: \
		current_offset+fixup_data_length])
	current_offset += fixup_data_length
	printFixupData(fixup_data)

	# replace fixup signature values with original values
	data_bytes = revertFixupData(data_bytes, fixup_data, MFT_ENTRY_LENGTH)

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
			= readAttr(data_bytes[current_offset:])
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
			printResAttr(res_attr_header, attr_content)
			attr_list.append([res_attr_header, attr_content])
		else:
			printNonResAttr(nonres_attr_header, attr_runlist)
			attr_list.append([nonres_attr_header, attr_runlist])

if __name__ == "__main__": main()
