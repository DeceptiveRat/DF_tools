from dataclasses import dataclass
import subprocess
import sys

import pretty_print as pp
from get_boundary import getBoundary
import file_reference_address as fra

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

@dataclass 
class DirectoryIndexEntry:
	MFT_file_reference: int
	entry_len: int 
	content_len: int
	flags: int
	file_name_attr: bytes
	padding2: bytes
	child_VCN: int

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
	pp.prettyPrint("Signature", index_record_header.signature, "hex")
	pp.prettyPrint("Fixup array offset", index_record_header.fixup_array_offset, "int")
	pp.prettyPrint("Fixup entry count", index_record_header.fixup_entry_count, "int")
	pp.prettyPrint("$LogFile seq num", index_record_header.logfile_seq_num, "int")
	pp.prettyPrint("Record VCN", index_record_header.record_VCN, "int")
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
	pp.prettyPrint("Entry start offset", index_node_header.entry_start_offset, "int")
	pp.prettyPrint("Entry end offset", index_node_header.entry_end_offset, "int")
	pp.prettyPrint("List buffer end offset", index_node_header.buffer_end_offset, "int")
	pp.prettyPrint("Flags", index_node_header.flags, "hex")
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

def printIndexEntry(index_entry, deleted, is_directory):
	if deleted:
		print("Delted ", end="")
	print("Index Entry", "="*15)
	if is_directory:
		pp.prettyPrint("MFT file reference", index_entry.MFT_file_reference, "hex", 16)
		fra.printFileReferenceAddress(index_entry.MFT_file_reference)
	else:
		print("First padding:")
		subprocess.run("xxd", input=index_entry.padding)
	pp.prettyPrint("Entry length", index_entry.entry_len, "int")
	pp.prettyPrint("Content length", index_entry.content_len, "int")
	pp.prettyPrint("Flags", index_entry.flags, "hex")
	if index_entry.flags & 0x01:
		print("\t- Child node flag set")
	if index_entry.flags & 0x02:
		print("\t- Last entry flag set")
	if is_directory:
		print("$FILE_NAME attribute:")
		subprocess.run("xxd", input=index_entry.file_name_attr)
	else:
		print("Content:")
		subprocess.run("xxd", input=index_entry.content)
	pp.prettyPrint("Child node VCN", index_entry.child_VCN, "int")
	print("Second padding:")
	subprocess.run("xxd", input=index_entry.padding2)
	print("\n\n")
