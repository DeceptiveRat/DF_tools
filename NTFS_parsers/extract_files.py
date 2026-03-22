#!/bin/python3 

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("-h: display this help screen")
	print("-e <int>,<int>,...:[Required] MFT entries to extract.")
	print("-m <int>:[Required] sector offset of $MFT.")
	
def main():
	try:
		opts, args = getopt.getopt(sys.argv[1:], "he:")
	except getopt.GetoptError as err:
		print(err)
		usage()
		sys.exit(-1)

	entry_number_list = []

	for option, argument in opts:
		if option == "-h":
			usage()
			sys.exit()
		elif option == "-e":
			for _ in argument.split(","):
				entry_number_list.append(_)
		else:
			assert False, "unhandled option"
	
	# parse $MFT

	# calculate offset of entries given

	# parse entries and get names

	# export entries with respective names

if __name__ == "__main__": main()
