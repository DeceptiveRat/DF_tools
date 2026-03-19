def prettyPrint(field, value, data_type, padding=-1):
	if data_type == "int":
		print("%-20s: %d" %(field, value))
	elif data_type == "hex":
		if padding != -1:
			print("%-20s:" %(field), end="")
			print(f"0x{value:0{padding}x}")
		else:
			print("%-20s: 0x%x" %(field, value))
	elif data_type == "bytes":
		print("%-20s:\n" %(field))
		print(value)
	elif data_type == "string":
		print("%-20s: %s" %(field, value))
