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
