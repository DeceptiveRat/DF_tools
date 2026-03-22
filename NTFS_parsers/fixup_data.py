from dataclasses import dataclass 
import sys

import pretty_print as pp

@dataclass 
class FixupData:
	fixup_value: bytes
	original_value_array: list[int]

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
	pp.prettyPrint("fixup value:", int.from_bytes(fixup_data.fixup_value), "hex")
	print("original value list: ")
	for _ in range(len(fixup_data.original_value_array)):
		print("\t- 0x%s" %(fixup_data.original_value_array[_].hex()))
	print("\n\n")

def revertFixupData(data_bytes, fixup_data, data_length):
	fixed_data_bytes = bytearray(data_bytes)
	for offset in range(510, data_length, 512):
		# doesn't match
		if data_bytes[offset:offset+2] != fixup_data.fixup_value:
			print("Warning: value at end of sector %d does not match fixup signature" \
				%((offset/512)+1), file=sys.stderr)
			print("Signature value: 0x%s\tValue at end of sector %d: 0x%s" \
				%(fixup_data.fixup_value.hex(), ((offset/512)+1), \
				data_bytes[offset:offset+2].hex()), file=sys.stderr)

		# fix value
		fixed_data_bytes[offset:offset+2] = fixup_data.original_value_array[0]

	return bytes(fixed_data_bytes)
