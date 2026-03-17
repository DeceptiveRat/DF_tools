#!/bin/python3 

import sys
import getopt

def usage():
	print("usage:", sys.argv[0])
	print("options:")
	print("-h: display this help screen")
	print("-d <int>: date in bytes")
	print("-t <int>: time in bytes")
	print("-x: bytes given in hex")

try:
	opts, args = getopt.getopt(sys.argv[1:], "hd:t:x")
except getopt.GetoptError as err:
	print(err)
	usage()
	sys.exit(2)

date_input = ""
time_input = ""
date_bytes = 0
time_bytes = 0
is_hex = False

for option, argument in opts:
	if option == "-h":
		usage()
		sys.exit()
	elif option == "-d":
		date_input = argument 
	elif option == "-t":
		time_input = argument
	elif option == "-x":
		is_hex = True
	else:
		assert False, "unhandled option"

if is_hex:
	if date_input:
		date_bytes = int(date_input, base=16)
	elif time_input:
		time_bytes = int(time_input, base=16)
else:
	if date_input:
		date_bytes = int(date_input, base=10)
	elif time_input:
		time_bytes = int(time_input, base=10)
	
if date_bytes:
	year = 1980 + ((date_bytes&0xFE00)>>9)
	month = (date_bytes&0x1E0)>>5
	day = (date_bytes&0x1f)
	if year < 0: 
		print("Wrong year value")
		exit()
	elif month<0 or month >12:
		print("Wrong month value")
		exit()
	elif day<0 or day>31:
		print("Wrong day value")
		exit()
	else:
		print("%d/%d/%d" %(year, month, day))

if time_bytes:
	hour = (time_bytes&0xf800)>>11
	minute = (time_bytes&0x7e0)>>5
	second = (time_bytes&0x1f)*2
	if hour < 0 or hour > 24:
		print("Wrong hour value")
		exit()
	elif minute<0 or minute>60:
		print("Wrong minute value")
		exit()
	elif second<0 or second>60:
		print("Wrong second value")
		exit()
	else: 
		print("%d:%d:%d" %(hour, minute, second))
