def getBoundary(start_byte, boundary_size):
	if start_byte%boundary_size == 0:
		return start_byte
	else:
		return start_byte + (boundary_size - (start_byte%boundary_size))
