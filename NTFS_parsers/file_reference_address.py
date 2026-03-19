import pretty_print as pp

def printFileReferenceAddress(file_reference_address):
	pp.prettyPrint("Sequence Number", file_reference_address>>48, "int")
	pp.prettyPrint("MFT entry address", (file_reference_address&0xfff), "int")
