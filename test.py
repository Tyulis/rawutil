from rawutil import *


def test_parser():
	print("\n===========\nTesting parser")
	ok_flat = "<2B 4n 16a 4s 4x 10c hHIQq6? | i2suU 8a $"
	ok_references = "2H /0n #0I 2B /p2s"
	ok_group = "2h (2B) 4[HIn] {4B4b}"
	ok_nested = "I 160[I 12s (4I) 4[I(2Bh)]]"
	ok_comments = """
		4s    'magic'
		I     'number of strings'
		/1(n) 'strings'
	"""
	ok_everything = ">4sI /1(I /p1s /0[I2B4a])"
	bad_noref = "@4sI /(12s)"
	bad_character = "4s2I /0[2I 4` 5H 4a]"
	bad_multiple = "4I 4{2B}"
	bad_multiple_ref = "2U /0|"
	
	print("\nFlat structure : " + ok_flat)
	ok1 = Struct(ok_flat)
	print(ok1.pprint(), "\nOK")
	
	print("\nReferences : " + ok_references)
	ok2 = Struct(ok_references)
	print(ok2.pprint(), "\nOK")
	
	print("\nGroups : " + ok_group)
	ok3 = Struct(ok_group)
	print(ok3.pprint(), "\nOK")
	
	print("\nNested groups : " + ok_nested)
	ok4 = Struct(ok_nested)
	print(ok4.pprint(), "\nOK")
	
	print("\nComments : " + ok_comments)
	ok5 = Struct(ok_comments)
	print(ok5.pprint(), "\nOK")
	
	print("\nAll at once : " + ok_everything)
	ok6 = Struct(ok_everything)
	print(ok6.pprint(), "\nOK")
	
	try:
		print("\nNo ref number error detection : " + bad_noref)
		Struct(bad_noref)
		print("! FAILED ! No error raised")
	except FormatError as e:
		print("OK : " + str(e))
	
	try:
		print("\nBad character error detection : " + bad_character)
		Struct(bad_character)
		print("! FAILED ! No error raised")
	except FormatError as e:
		print("OK : " + str(e))
		
	try:
		print("\nBad multiple element detection : " + bad_multiple)
		Struct(bad_multiple)
		print("! FAILED ! No error raised")
	except FormatError as e:
		print("OK : " + str(e))
	
	try:
		print("\nBad multiple element with reference detection : " + bad_multiple_ref)
		Struct(bad_multiple_ref)
		print("! FAILED ! No error raised")
	except FormatError as e:
		print("OK : " + str(e))

def test_unpack_bytes():
	print("\n===========\nTest unpack bytes")
	stct1 = Struct("<4sIx /1(n4a) 4Xxx ??c b /p1[B /0(B)4a] $")
	data1 = b"TEST\x03\x00\x00\x00\x00test\x00\x00\x00\x00test2\x00\x00\x00newtest\x00\xab\xcd\xef\xff\x00\x00\x01\x00x\x02\x02\x10\x11\x00\x03\x12\x13\x14ABCDEF"
	outp1 = [b"TEST", 3, [b"test", b"test2", b"newtest"], "abcdefff", True, False, b"x", 2, [[2, [16, 17]], [3, [18, 19, 20]]], b"ABCDEF"]
	
	stct2 = Struct("<2e2f2d")
	data2 = b"\xfcw\xf0<\x02\x00\x00\x00K\x06\x9e?\xf2Q\x8cB\xca\xc0\xf3?UPQ\xf5+\x05$@"
	outp2 = [32704.0, 1.234375, 2.802596928649634e-45, 1.2345670461654663, 1.234567890123, 10.010101]
	
	print("\nStructure 1 : " + stct1.format)
	testout1 = stct1.unpack(data1)
	if outp1 == testout1:
		print("OK")
	else:
		print("! FAILED ! Unpack output and control data do not match")
		print("Output  : ", testout1)
		print("Control : ", outp1)
	
	print("\nStructure 2 : " + stct2.format)
	testout2 = stct2.unpack(data2)
	if outp2 == testout2:
		print("OK")
	else:
		print("! FAILED ! Unpack output and control data do not match")
		print("Output  : ", testout2)
		print("Control : ", outp2)
	
	badstct1 = Struct(">4sI /0(n4a) 4X $")
	
	try:
		print("\nReference on non-integer value detection : " + badstct1.format)
		badstct1.unpack(data1)
		print("! FAILED ! No error raised")
	except OperationError as e:
		print("OK : " + str(e))

def test_pack_bytes():
	print("\n===========\nTest pack bytes")
	stct1 = Struct("<4sIx /1(n4a) 4Xxx ??c b /p1[B /0(B)4a] $")
	data1 = b"TEST\x03\x00\x00\x00\x00test\x00\x00\x00\x00test2\x00\x00\x00newtest\x00\xab\xcd\xef\xff\x00\x00\x01\x00x\x02\x02\x10\x11\x00\x03\x12\x13\x14ABCDEF"
	outp1 = [b"TEST", 3, [b"test", b"test2", b"newtest"], "abcdefff", True, False, b"x", 2, [[2, [16, 17]], [3, [18, 19, 20]]], b"ABCDEF"]
	
	stct2 = Struct("<2e2f2d")
	data2 = b"\xfcw\xf0<\x02\x00\x00\x00K\x06\x9e?\xf2Q\x8cB\xca\xc0\xf3?UPQ\xf5+\x05$@"
	outp2 = [32704.0, 1.234375, 2.802596928649634e-45, 1.2345670461654663, 1.234567890123, 10.010101]
	
	print("\nStructure 1 : " + stct1.format)
	testout1 = stct1.pack(*outp1)
	if data1 == testout1:
		print("OK")
	else:
		print("! FAILED ! Unpack output and control data do not match")
		print("Output  : ", testout1)
		print("Control : ", data1)
	
	print("\nStructure 2 : " + stct2.format)
	testout2 = stct2.pack(*outp2)
	if data2 == testout2:
		print("OK")
	else:
		print("! FAILED ! Unpack output and control data do not match")
		print("Output  : ", testout2)
		print("Control : ", data2)

def test_calcsize():
	print("\n===========\nTest calcsize")
	okstruct = Struct("4sI |2B 7s2x 16a")
	okstructsize = 24
	badstructref = Struct("4sI /1(2I)")
	badstructstr = Struct("4sI 10[2n]")
	
	print("\nStructure 1 : " + okstruct.format)
	size = okstruct.calcsize()
	if size == okstructsize:
		print("OK")
	else:
		print("! FAILED ! Output : " + str(size) + ", control : " + str(okstructsize))
	
	try:
		print("\nReference detection : " + badstructref.format)
		badstructref.calcsize()
		print("! FAILED ! No error raised")
	except FormatError as e:
		print("OK : " + str(e))
	
	try:
		print("\nNull-terminated string detection : " + badstructstr.format)
		badstructstr.calcsize()
		print("! FAILED ! No error raised")
	except FormatError as e:
		print("OK : " + str(e))

def test_operations():
	part1 = Struct("<4s")
	part2 = Struct("I /0(#0B #0b)")
	part3 = Struct("I /0s #0a")
	added_expect = "<4s I /1(#0B #0b) I /3s #1a"
	multiplied_expect = "<I /0(#0B #0b) I /2(#1B #1b) I /4(#2B #2b)"
	
	print("\nAdding p1 + p2 + p3")
	added = part1 + part2 + part3
	if added.format == added_expect:
		print("OK")
	else:
		print("! FAILED ! Output : \"" + added.format + "\", control : \"" + added_expect + "\"")
	
	print("\nMultiply p2*3")
	multiplied = part2 * 3
	if multiplied.format == multiplied_expect:
		print("OK")
	else:
		print("! FAILED ! Output : \"" + multiplied.format + "\", control : \"" + multiplied_expect + "\"")
	

if __name__ == "__main__":  # Tests
	print("Running tests")
	test_parser()
	test_unpack_bytes()
	test_pack_bytes()
	test_calcsize()
	test_operations()