#!/bin/python3 

import sys
import getopt

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("-h: display this help screen")
	print("-f <file name>: [required] image file")
	print("-o <int>: [optional] offset of FAT file system in image")
	print("-e <int>: [required] offset of directory entry from start of FS")
	print("-v <12/16/32>: [optional] FAT version. Default is 32")

try:
	opts, args = getopt.getopt(sys.argv[1:], "hf:o:e:v:")
except getopt.GetoptError as err:
	print(err)
	usage()
	sys.exit(2)

file_name =""
FS_offset = 0
entry_offset = 0
FAT_version = 32
output_file_name = "extracted_file.dat"

for option, argument in opts:
	if option == "-h":
		usage()
		sys.exit()
	elif option == "-f":
		file_name = argument
	elif option == "-o":
		FS_offset = int(argument)
	elif option == "-e":
		entry_offset = int(argument)
	elif option == "-v":
		FAT_version = int(argument)
	else:
		assert False, "unhandled option"

if FAT_version not in [12, 16, 32]:
	usage()
	sys.exit(2)

if FAT_version != 32:
	print("FAT versions 12 and 16 not supported yet...")
	sys.exit(2)
	
if file_name == "":
	usage()
	sys.exit(2)

boot_sector = b""
sector_size = 0
sector_per_cluster = 0
FAT_offset = 0
FAT_size = 0
FAT_structure = b""
target_entry = b""
target_size = 0

# read boot sector, FAT structure, and the target entry
with open(file_name, "rb") as file:
	file.seek(FS_offset, 0)
	boot_sector = file.read(90)
	sector_size = int.from_bytes(boot_sector[11:13], byteorder="little")
	sector_per_cluster = int.from_bytes(boot_sector[13:14], byteorder="little")
	FAT_offset = int.from_bytes(boot_sector[14:16], byteorder="little")*sector_size
	FAT_size = int.from_bytes(boot_sector[36:40], byteorder="little")*sector_size
	file.seek(FS_offset + FAT_offset, 0)
	FAT_structure = file.read(FAT_size)
	file.seek(FS_offset + entry_offset, 0)
	target_entry = file.read(32)
	target_size = int.from_bytes(target_entry[28:32], byteorder="little")

remaining_bytes = target_size
cluster_size = sector_size *sector_per_cluster

print(f"sector size in bytes: {sector_size}")
print(f"cluster size in bytes: {cluster_size}")

# get address of first cluster
cluster_address_upper = int.from_bytes(target_entry[20:22], byteorder="little")<<16
print(cluster_address_upper)
cluster_address_lower = int.from_bytes(target_entry[26:28], byteorder="little")
print(cluster_address_lower)
next_cluster_address = cluster_address_upper + cluster_address_lower

print(f"first cluster address: {next_cluster_address}")

# extract file content
with open(output_file_name, "wb") as out_file:
	with open(file_name, "rb") as in_file:
		if remaining_bytes > cluster_size:
			buffer = in_file.read(cluster_size)
			remaining_bytes-= cluster_size
		else:
			buffer = in_file.read(remaining_bytes)
			remaining_bytes = 0

	out_file.write(buffer)
	
count = 0
while remaining_bytes > 0 and count < 2:
	next_cluster_address = int.from_bytes(FAT_structure[next_cluster_address*4:next_cluster_address*4 + 4], byteorder="big")
	print(f"next cluster address: {next_cluster_address}")
	count+=1

	# extract file content
	with open(output_file_name, "ab") as out_file:
		with open(file_name, "rb") as in_file:
			if remaining_bytes > cluster_size:
				buffer = in_file.read(cluster_size)
				remaining_bytes-= cluster_size
			else:
				buffer = in_file.read(remaining_bytes)
				remaining_bytes = 0

		out_file.write(buffer)
