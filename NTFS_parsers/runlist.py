from dataclasses import dataclass

@dataclass 
class Runlist:
	run_length: int
	run_offset: int

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
