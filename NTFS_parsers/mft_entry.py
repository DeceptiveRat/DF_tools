from dataclasses import dataclass
import sys

import pretty_print as pp
import runlist as rl

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
	pp.prettyPrint("fixup array offset", entry_header.fixup_array_offset, "int")
	pp.prettyPrint("fixup entry count", entry_header.fixup_entry_count, "int")
	pp.prettyPrint("$LogFile seq num", entry_header.logfile_seq_num, "int")
	pp.prettyPrint("sequence value", entry_header.seq_value, "int")
	pp.prettyPrint("link count", entry_header.link_count, "int")
	pp.prettyPrint("attribute offset", entry_header.attr_offset, "int")
	if entry_header.flags & 0x01:
		print("flags: in use flag set")
	if entry_header.flags & 0x02:
		print("flags: directory flag set")
	pp.prettyPrint("MFT entry used size", entry_header.entry_used_size, "int")
	pp.prettyPrint("MFT entry allocated size", entry_header.entry_alloc_size, "int")
	pp.prettyPrint("file reference to base record", entry_header.base_record_file_ref \
		, "int")
	pp.prettyPrint("next attribute id", entry_header.next_attr_id, "int")
	print("\n\n")

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
	pp.prettyPrint("attribute length", attr_header.attr_len, "int")
	if attr_header.non_resident_flag == 1:
		pp.prettyPrint("non resident flag", "non-resident flag set", "string")
	else:
		pp.prettyPrint("non resident flag", "non-resident flag not set", "string")
	pp.prettyPrint("name length", attr_header.name_len, "int")
	pp.prettyPrint("name offset", attr_header.name_offset, "int")
	print("flags set:")
	if attr_header.flags & 0x01: 
		print("\t- compressed flag set")
	if attr_header.flags & 0x4000:
		print("\t- encrypted flag set")
	if attr_header.flags & 0x8000:
		print("\t- sparse flag set")
	pp.prettyPrint("attribute id", attr_header.attr_id, "int")

def readResAttrHeader(data_bytes) -> ResAttrHeader:
	content_size = int.from_bytes(data_bytes[0:4], "little")
	content_offset = int.from_bytes(data_bytes[4:6], "little")
	return ResAttrHeader(None, content_size, content_offset)

def printResAttrHeader(res_attr_header):
	printAttrHeader(res_attr_header.attr_header)
	pp.prettyPrint("content size:", res_attr_header.content_size, "int")
	pp.prettyPrint("content offset:", res_attr_header.content_offset, "int")

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
	pp.prettyPrint("runlist starting VCN", nonres_attr_header.runlist_start_VCN, "int")
	pp.prettyPrint("runlist end VCN", nonres_attr_header.runlist_end_VCN, "int")
	pp.prettyPrint("runlist offset", nonres_attr_header.runlist_offset, "int")
	pp.prettyPrint("compression unit size", nonres_attr_header.compression_unit_size, \
		"int")
	pp.prettyPrint("content allocated size", \
		nonres_attr_header.attr_content_alloc_size, "int")
	pp.prettyPrint("content actual size", \
		nonres_attr_header.attr_content_actual_size, "int")
	pp.prettyPrint("content initialized size", \
		nonres_attr_header.attr_content_init_size, "int")

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
		attr_runlist, read_bytes = rl.readRunlist(data_bytes[current_offset:])
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
		print("\tRunlist[%d]:\tRun Length: %d\t\t\tRun Offset: %d(%d from start \
			of FS)" %(_, attr_runlist[_].run_length, attr_runlist[_].run_offset, \
			cumulated_offset))

	print("Content:")
	# print content

	print("\n\n")
