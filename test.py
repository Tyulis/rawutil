import sys
import math
import unittest
import rawutil


class StructureTestCase (unittest.TestCase):
	simple_bothways = {
		"<b": [(0, b"\x00"), (1, b"\x01"), (60, b"\x3C"), (127, b"\x7F"), (-1, b"\xFF"), (-60, b"\xC4"), (-128, b"\x80"),
		       (128, OverflowError), (-129, OverflowError), (rawutil.DataError, b"")],
		"<B": [(0, b"\x00"), (1, b"\x01"), (60, b"\x3C"), (128, b"\x80"), (255, b"\xFF"),
		       (-1, OverflowError), (256, OverflowError), (rawutil.DataError, b"")],
		"<h": [(0, b"\x00\x00"), (1, b"\x01\x00"), (256, b"\x00\x01"), (32767, b"\xFF\x7F"), (-1, b"\xFF\xFF"), (-1000, b"\x18\xFC"), (-32768, b"\x00\x80"),
		       (32768, OverflowError), (-32769, OverflowError), (rawutil.DataError, b"X")],
		"<H": [(0, b"\x00\x00"), (1, b"\x01\x00"), (256, b"\x00\x01"), (65535, b"\xFF\xFF"),
		       (-1, OverflowError), (65536, OverflowError), (rawutil.DataError, b"X")],
		"<u": [(0, b"\x00\x00\x00"), (1, b"\x01\x00\x00"), (256, b"\x00\x01\x00"), (65536, b"\x00\x00\x01"), (8388607, b"\xFF\xFF\x7F"), (-1, b"\xFF\xFF\xFF"), (-8388608, b"\x00\x00\x80"),
		       (8388608, OverflowError), (-8388609, OverflowError), (rawutil.DataError, b"XX")],
		"<U": [(0, b"\x00\x00\x00"), (1, b"\x01\x00\x00"), (256, b"\x00\x01\x00"), (65536, b"\x00\x00\x01"), (16777215, b"\xFF\xFF\xFF"),
		       (-1, OverflowError), (16777216, OverflowError), (rawutil.DataError, b"XX")],
		"<i": [(0, b"\x00\x00\x00\x00"), (1, b"\x01\x00\x00\x00"), (256, b"\x00\x01\x00\x00"), (65536, b"\x00\x00\x01\x00"), (2147483647, b"\xFF\xFF\xFF\x7F"),
		       (-1, b"\xFF\xFF\xFF\xFF"), (-2147483648, b"\x00\x00\x00\x80"),
		       (2147483648, OverflowError), (-2147483649, OverflowError), (rawutil.DataError, b"BAD")],
		"<I": [(0, b"\x00\x00\x00\x00"), (1, b"\x01\x00\x00\x00"), (256, b"\x00\x01\x00\x00"), (65536, b"\x00\x00\x01\x00"), (4294967295, b"\xFF\xFF\xFF\xFF"),
		       (-1, OverflowError), (4294967296, OverflowError), (rawutil.DataError, b"BAD")],
		"<q": [(0, b"\x00\x00\x00\x00\x00\x00\x00\x00"), (1, b"\x01\x00\x00\x00\x00\x00\x00\x00"), (4294967295, b"\xFF\xFF\xFF\xFF\x00\x00\x00\x00"), (2**63-1, b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x7F"),
		       (-1, b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"), (-2**63, b"\x00\x00\x00\x00\x00\x00\x00\x80"),
		       (2**63, OverflowError), (-2**63-1, OverflowError), (rawutil.DataError, b"2-SHORT")],
		"<Q": [(0, b"\x00\x00\x00\x00\x00\x00\x00\x00"), (1, b"\x01\x00\x00\x00\x00\x00\x00\x00"), (65536, b"\x00\x00\x01\x00\x00\x00\x00\x00"),
		       (4294967295, b"\xFF\xFF\xFF\xFF\x00\x00\x00\x00"), (2**64-1, b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"),
		       (2**64, OverflowError), (-1, OverflowError), (rawutil.DataError, b"2.SHORT")],
		
		# At least for now, floating-point numbers should follow the `struct` module behaviour, especially regarding NaN and rounding
		"<e": [(0, b"\x00\x00"), (1, b"\x00\x3C"), ((1+24/1024)/1024, b"\x18\x14"), (2**-14/1024, b"\x01\x00"), ((1023/1024)*2**-14, b"\xFF\x03"), (2**-14, b"\x00\x04"), (65504, b"\xFF\x7B"),
		       (math.inf, b"\x00\x7C"), (-1, b"\x00\xBC"), (-math.inf, b"\x00\xFC"),
		       (65519.999999999997, OverflowError), (rawutil.DataError, b"X")],
		"<f": [(0, b"\x00\x00\x00\x00"), (1, b"\x00\x00\x80\x3F"), ((1+100/2**23)/1024, b"\x64\x00\x80\x3a"), (2**-149, b"\x01\x00\x00\x00"), ((1-2**-23) * 2**-126, b"\xFF\xFF\x7F\x00"),
		       (2**-126, b"\x00\x00\x80\x00"), (2**127 * (2-2**-23), b"\xFF\xFF\x7F\x7F"), (math.inf, b"\x00\x00\x80\x7F"), (-1, b"\x00\x00\x80\xBF"), (-math.inf, b"\x00\x00\x80\xFF"),
		       (2**127 * (2-2**-23.999999998), OverflowError), (rawutil.DataError, b"BAD")],
		"<d": [(0, b"\x00\x00\x00\x00\x00\x00\x00\x00"), (1, b"\x00\x00\x00\x00\x00\x00\xF0\x3F"), ((1+100/2**52)/1024, b"\x64\x00\x00\x00\x00\x00\x50\x3f"), (2**-1074, b"\x01\x00\x00\x00\x00\x00\x00\x00"),
		       ((1-2**-52) * 2**-1022, b"\xFF\xFF\xFF\xFF\xFF\xFF\x0F\x00"), (2**-1022, b"\x00\x00\x00\x00\x00\x00\x10\x00"), (2**1023 * (2-2**-52), b"\xFF\xFF\xFF\xFF\xFF\xFF\xEF\x7F"),
		       (math.inf, b"\x00\x00\x00\x00\x00\x00\xF0\x7F"), (-1, b"\x00\x00\x00\x00\x00\x00\xF0\xBF"), (-math.inf, b"\x00\x00\x00\x00\x00\x00\xF0\xFF"),
		       (rawutil.DataError, b"2.SHORT")],
		# Too large to test the limit with floats. TODO : Check with decimals
		"<F": [(0, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"), (1, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x3F"),
		       (math.inf, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\x7F"), (-1, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xBF"),
		       (-math.inf, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF"),
		       (rawutil.DataError, b"ThisIsTooShort")],
		"<c": [(b"a", b"a"), (b"\x00", b"\x00"), (b"\xFF", b"\xFF"),
		       (rawutil.DataError, b"")],
		"<?": [(False, b"\x00"), (True, b"\x01"),
		       (rawutil.DataError, b"")],
	}
	
	simple_pack = {
		"<e": [((1+47/2048)/1024, b"\x18\x14"), ((1+49/2048)/1024, b"\x18\x14"), ((1+99/4096)/1024, b"\x19\x14"), (65519.999999999996, b"\xFF\x7B")],
		"<f": [((1+199/2**24)/1024, b"\x64\x00\x80\x3A"), ((1+201/2**24)/1024, b"\x64\x00\x80\x3A"), (2**127 * (2-2**-23.999999997), b"\xFF\xFF\x7F\x7F"), ],
		"<d": [((1+199/2**53)/1024, b"\x64\x00\x00\x00\x00\x00\x50\x3f"), ((1+201/2**53)/1024, b"\x64\x00\x00\x00\x00\x00\x50\x3f")],  # Upper limit yields a Python math.inf here. Todo : check with Decimals
	}
	
	simple_unpack = {
		"<?": [(True, b"\x02"), (True, b"\x10"), (True, b"\xFF")],
	}
	
	# Here, the first value is the one that is output when packing math.nan
	nan_values = {
		"<e": [(math.nan, b"\x00\x7E"), (math.nan, b"\xFF\xFF"), (math.nan, b"\xFF\x7F")],
		"<f": [(math.nan, b"\x00\x00\xC0\x7F"), (math.nan, b"\xFF\xFF\xFF\xFF"), (math.nan, b"\xFF\xFF\xFF\x7F")],
		"<d": [(math.nan, b"\x00\x00\x00\x00\x00\x00\xF8\x7F"), (math.nan, b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"), (math.nan, b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x7F")],
	}
	
	
	@classmethod
	def setUpClass(cls):
		# Add all byte order marks and format aliases
		cls.setup_number_tests(cls.simple_bothways)
		cls.setup_number_tests(cls.simple_pack)
		cls.setup_number_tests(cls.simple_unpack)
		cls.setup_number_tests(cls.nan_values)
	
	@classmethod
	def setup_number_tests(cls, tests):
		systemmark = rawutil.ENDIANMARKS[sys.byteorder]
		for structure, cases in list(tests.items()):
			structmark = structure[0]
			invertmark = ">" if structmark == "<" else ">"
			reverse_struct = structure.replace(structmark, invertmark)
			tests[reverse_struct] = [(unpacked, bytes(reversed(packed)) if not isinstance(packed, type) else packed) for unpacked, packed in cases]
			if systemmark == structmark:
				tests[structure.replace(structmark, "")] = tests[structure]
				tests[structure.replace(structmark, "=")] = tests[structure]
				tests[structure.replace(structmark, "@")] = tests[structure]
			else:
				tests[structure.replace(structmark, "")] = tests[reverse_struct]
				tests[structure.replace(structmark, "=")] = tests[reverse_struct]
				tests[structure.replace(structmark, "@")] = tests[reverse_struct]
			tests[structure.replace(structmark, "!")] = tests[structure.replace(structmark, ">")]
		for structure, cases in list(tests.items()):
			if "i" in structure:
				tests[structure.replace("i", "l")] = cases
			if "I" in structure:
				tests[structure.replace("I", "L")] = cases

	
	def test_simple_bothways(self):
		for structure, cases in self.simple_bothways.items():
			for unpacked, packed in cases:
				with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
					if isinstance(packed, type):
						with self.assertRaises(packed):
							rawutil.pack(structure, unpacked)
					elif isinstance(unpacked, type):
						with self.assertRaises(unpacked):
							rawutil.unpack(structure, packed)
					else:
						self.assertEqual(rawutil.unpack(structure, packed)[0], unpacked)
						self.assertEqual(rawutil.pack(structure, unpacked), packed)
	
	def test_simple_pack(self):
		for structure, cases in self.simple_pack.items():
			for unpacked, packed in cases:
				with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
					self.assertEqual(rawutil.pack(structure, unpacked), packed)
	
	def test_simple_unpack(self):
		for structure, cases in self.simple_unpack.items():
			for unpacked, packed in cases:
				with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
					self.assertEqual(rawutil.unpack(structure, packed)[0], unpacked)
	
	def test_nan(self):
		for structure, cases in self.nan_values.items():
			with self.subTest(structure=structure, case=cases[0][1], bothways=True):
				self.assertTrue(math.isnan(rawutil.unpack(structure, cases[0][1])[0]))
				self.assertEqual(rawutil.pack(structure, math.nan), cases[0][1])
			for unpacked, packed in cases[1:]:
				self.assertTrue(math.isnan(rawutil.unpack(structure, packed)[0]))
	
	def test_void(self):
		for byteorder in rawutil.ENDIANNAMES:
			with self.subTest(part="packing", byteorder=byteorder):
				self.assertEqual(rawutil.pack(byteorder + "x"), b"\x00")
				self.assertEqual(rawutil.pack(byteorder + "5x"), b"\x00\x00\x00\x00\x00")
				self.assertEqual(rawutil.pack(byteorder + "xc", b"Z"), b"\x00Z")
				self.assertEqual(rawutil.pack(byteorder + "cx", b"A"), b"A\x00")
				self.assertEqual(rawutil.pack(byteorder + "cxc", b"A", b"Z"), b"A\x00Z")
		
			with self.subTest(part="unpacking", byteorder=byteorder):
				#with self.assertRaises(rawutil.DataError):
				self.assertEqual(len(rawutil.unpack(byteorder + "x", b"")), 0)
				self.assertEqual(len(rawutil.unpack(byteorder + "x", b"\x00")), 0)
				self.assertEqual(len(rawutil.unpack(byteorder + "5x", b"\x00\x00\x00\x00\x00")), 0)
				self.assertSequenceEqual(rawutil.unpack(byteorder + "xc", b"\x00Z"), [b"Z"])
				self.assertSequenceEqual(rawutil.unpack(byteorder + "cx", b"A\x00"), [b"A"])
				self.assertSequenceEqual(rawutil.unpack(byteorder + "cxc", b"A\x00Z"), [b"A", b"Z"])
	
	def test_repeat_immediate(self):
		# Test cases are generated by concatenating simple test cases
		for structure, cases in self.simple_bothways.items():
			result_cases = [case for case in cases if not isinstance(case[0], type) and not isinstance(case[1], type)]
			for count in (0, 1, len(result_cases)):
				repeated = structure[:-1] + str(count) + structure[-1:]
				packed = b"".join(case[1] for case in result_cases[:count])
				unpacked = [case[0] for case in result_cases[:count]]
				with self.subTest(structure=repeated, packed=packed, unpacked=unpacked):
					self.assertSequenceEqual(rawutil.unpack(repeated, packed), unpacked)
					self.assertEqual(rawutil.pack(repeated, *unpacked), packed)
	
	def test_repeat_reference(self):
		# Test case are generated by concatenating simple test cases and adding a few bytes in front
		for structure, cases in self.simple_bothways.items():
			result_cases = [case for case in cases if not isinstance(case[0], type) and not isinstance(case[1], type)]
			for count in (0, 1, len(result_cases)):
				for position in (0, 1, 2):
					repeated = structure[:-1] + "4B /" + str(position) + structure[-1:]
					header = [count if i == position else 0xFF for i in range(4)]
					packed = bytes(header) + b"".join(case[1] for case in result_cases[:count])
					unpacked = header + [case[0] for case in result_cases[:count]]
					with self.subTest(part="valid", structure=repeated, packed=packed, unpacked=unpacked):
						self.assertSequenceEqual(rawutil.unpack(repeated, packed), unpacked)
						self.assertEqual(rawutil.pack(repeated, *unpacked), packed)
				
	def test_repeat_relative(self):
		# Test case are generated by concatenating simple test cases and adding a few bytes in front
		for structure, cases in self.simple_bothways.items():
			result_cases = [case for case in cases if not isinstance(case[0], type) and not isinstance(case[1], type)]
			for count in (0, 1, len(result_cases)):
				for position in (1, 2, 3):
					repeated = structure[:-1] + "4B /p" + str(position) + structure[-1:]
					header = [count if i == 4-position else 0xFF for i in range(4)]
					packed = bytes(header) + b"".join(case[1] for case in result_cases[:count])
					unpacked = header + [case[0] for case in result_cases[:count]]
					with self.subTest(structure=repeated, packed=packed, unpacked=unpacked):
						self.assertSequenceEqual(rawutil.unpack(repeated, packed), unpacked)
						self.assertEqual(rawutil.pack(repeated, *unpacked), packed)
	
	def test_repeat_external(self):
		# Test case are generated by concatenating simple test cases and giving external references
		for structure, cases in self.simple_bothways.items():
			result_cases = [case for case in cases if not isinstance(case[0], type) and not isinstance(case[1], type)]
			for count in (0, 1, len(result_cases)):
				for position in (0, 1, 3):
					repeated = structure[:-1] + "#" + str(position) + structure[-1:]
					packed = b"".join(case[1] for case in result_cases[:count])
					unpacked = [case[0] for case in result_cases[:count]]
					refdata = [count if i == position else 0xFF for i in range(4)]
					with self.subTest(structure=repeated, packed=packed, unpacked=unpacked):
						self.assertSequenceEqual(rawutil.unpack(repeated, packed, refdata=refdata), unpacked)
						self.assertEqual(rawutil.pack(repeated, *unpacked, refdata=refdata), packed)
		
	def test_reference_absolute_error_referencing_itself(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("4B /4c")
	
	def test_reference_absolute_error_referencing_farther(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("4B /6c")
	
	def test_reference_absolute_error_bad_count_value(self):
		structure = "B /0B"
		unpacked = [0xFF, 33]
		packed = bytes(unpacked)
		with self.assertRaises(rawutil.DataError):
			rawutil.unpack(structure, packed)
		with self.assertRaises(rawutil.DataError):
			rawutil.pack(structure, *unpacked)

	def test_reference_absolute_error_bad_count_type(self):
		structure = "4s /0B"
		unpacked = [b"BAAD", 33]
		packed = b"BAAD!"
		with self.assertRaises(TypeError):
			rawutil.unpack(structure, packed)
		with self.assertRaises(TypeError):
			rawutil.pack(structure, *unpacked)
	
	def test_reference_absolute_inside_indeterminate_safe(self):		
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0B /1c")
	
	def test_reference_absolute_beyond_indeterminate_safe(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0B B /5c")
	
	def test_reference_absolute_inside_indeterminate_unsafe(self):
		unpacked = [4, 2, 0xFF, 0xFF, 0xFF, 33, 33]
		packed = bytes(unpacked)
		structobj = rawutil.Struct("B /0B /1B", safe_references=False)
		self.assertSequenceEqual(structobj.unpack(packed), unpacked)
		self.assertEqual(structobj.pack(*unpacked), packed)
		
	def test_reference_absolute_beyond_indeterminate_unsafe(self):
		unpacked = [4, 0xFF, 0xFF, 0xFF, 0xFF, 2, 33, 33]
		packed = bytes(unpacked)
		structobj = rawutil.Struct("B /0B B /5B", safe_references=False)
		self.assertSequenceEqual(structobj.unpack(packed), unpacked)
		self.assertEqual(structobj.pack(*unpacked), packed)
	
	def test_reference_relative_error_referencing_itself(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /p0B")
		
	def test_reference_relative_error_referencing_beyond_start(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /p2B")
	
	def test_reference_relative_inside_indeterminate_safe(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0B /p1B")
	
	def test_reference_relative_beyond_indeterminate_safe(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0B /p5B")
	
	def test_reference_relative_inside_indeterminate_unsafe(self):
		unpacked = [4, 0xFF, 0xFF, 0xFF, 2, 33, 33]
		packed = bytes(unpacked)
		structobj = rawutil.Struct("B /0B /p1B", safe_references=False)
		self.assertSequenceEqual(structobj.unpack(packed), unpacked)
		self.assertEqual(structobj.pack(*unpacked), packed)
		
	def test_reference_relative_beyond_indeterminate_unsafe(self):
		unpacked = [4, 0xFF, 0xFF, 0xFF, 0xFF, 33, 33, 33, 33]
		packed = bytes(unpacked)
		structobj = rawutil.Struct("B /0B /p5B", safe_references=False)
		self.assertSequenceEqual(structobj.unpack(packed), unpacked)
		self.assertEqual(structobj.pack(*unpacked), packed)
	
	def test_reference_external_error_bad_count_value(self):
		structure = "#0B"
		unpacked = [33]
		packed = bytes(unpacked)
		with self.assertRaises(rawutil.DataError):
			rawutil.unpack(structure, packed, refdata=[0xFF])
		with self.assertRaises(rawutil.DataError):
			rawutil.pack(structure, *unpacked, refdata=[0xFF])
	
	def test_reference_external_error_bad_count_type(self):
		structure = "#0B"
		unpacked = [33]
		packed = bytes(unpacked)
		with self.assertRaises(TypeError):
			rawutil.unpack(structure, packed, refdata=["BAAD"])
		with self.assertRaises(TypeError):
			rawutil.pack(structure, *unpacked, refdata=[b"BAAD"])
	
	def test_reference_external_error_bad_index(self):
		structure = "#1B"
		unpacked = [33]
		packed = bytes(unpacked)
		with self.assertRaises(rawutil.ResolutionError):
			rawutil.unpack(structure, packed, refdata=[1])
		with self.assertRaises(rawutil.ResolutionError):
			rawutil.pack(structure, *unpacked, refdata=[1])
	
	string_cases = [
		("<4s 4s", [b"DEAD", b"BEEF"], b"DEADBEEF"),
		(">4s 4s", [b"DEAD", b"BEEF"], b"DEADBEEF"),
		("B /0s", [4, b"SPAM"], b"\x04SPAM"),
		("B /p1s", [4, b"SPAM"], b"\x04SPAM"),
		(">3n", [b"spam", b"ham", b"eggs"], b"spam\x00ham\x00eggs\x00"),
		("<3n", [b"spam", b"ham", b"eggs"], b"spam\x00ham\x00eggs\x00"),
		("B /0n", [3, b"spam", b"ham", b"eggs"], b"\x03spam\x00ham\x00eggs\x00"),
		("B /p1n", [2, b"foo", b"bar"], b"\x02foo\x00bar\x00"),
		(">4X", ["deadbeef"], b"\xDE\xAD\xBE\xEF"),
		("<4X", ["deadbeef"], b"\xDE\xAD\xBE\xEF"),
		("B /0X", [4, "deadbeef"], b"\x04\xDE\xAD\xBE\xEF"),
		("B /p1X", [4, "deadbeef"], b"\x04\xDE\xAD\xBE\xEF"),
		("$", [b"spam"], b"spam"),
		("Bn $", [0xFF, b"spam", b"ham\x00eggs\x00"], b"\xFFspam\x00ham\x00eggs\x00"),
	]
	
	def test_string(self):
		for structure, unpacked, packed in self.string_cases:
			with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
				self.assertSequenceEqual(rawutil.unpack(structure, packed), unpacked)
				self.assertEqual(rawutil.pack(structure, *unpacked), packed)
	
	def test_dollar_error(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B$ B")
	
	def test_dollar_error_multiple(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B 2$")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0$")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /p1$")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B #0$")
	
	alignment_cases = [
		("BBBBB 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04\x00\x00\x00"),
		("|BBBBB 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04\x00\x00\x00"),
		("B|BBBB 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04"),
		("BB|BBB 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04\x00"),
		("BBB|BB 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04\x00\x00"),
		("BBBB|B 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04\x00\x00\x00"),
		("BBBBB| 4a", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04"),
		("BB|BBB", [0, 1, 2, 3, 4], b"\x00\x01\x02\x03\x04"),
		("B (BB 4a)", [1, [2, 3]], b"\x01\x02\x03\x00\x00"),
		("B (|BB 4a)", [1, [2, 3]], b"\x01\x02\x03\x00\x00"),
		("B (B|B 4a)", [1, [2, 3]], b"\x01\x02\x03\x00\x00\x00"),
		("B (BB| 4a)", [1, [2, 3]], b"\x01\x02\x03"),
		("B (B|B)", [1, [2, 3]], b"\x01\x02\x03"),
		("B (BB) 4a", [1, [2, 3]], b"\x01\x02\x03\x00"),
		("B |(BB) 4a", [1, [2, 3]], b"\x01\x02\x03\x00\x00"),
	]
	
	def test_alignment(self):
		for structure, unpacked, packed in self.alignment_cases:
			with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
				self.assertSequenceEqual(rawutil.unpack(structure, packed), unpacked)
				self.assertEqual(rawutil.pack(structure, *unpacked), packed)
	
	def test_pipe_error_multiple(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B 2| 4a")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0| 4a")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /p1| 4a")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B #0| 4a")
	
	group_cases = [
		("(2B 2c)", [[35, 33, b"A", b"B"]], b"#!AB"),
		("<(HH)", [[1, 32767]], b"\x01\x00\xFF\x7F"),
		(">(HH)", [[1, 32767]], b"\x00\x01\x7F\xFF"),
		("B (2c)", [33, [b"A", b"B"]], b"!AB"),
		("(2c) B", [[b"A", b"B"], 33], b"AB!"),
		("B (2c) B", [35, [b"A", b"B"], 33], b"#AB!"),
		("B (B ((B (2B) B) B))", [0, [1, [[2, [3, 4], 5], 6]]], b"\x00\x01\x02\x03\x04\x05\x06"),
		("6(B)", [[0, 1, 2, 3, 4, 5]], b"\x00\x01\x02\x03\x04\x05"),
		("3(B?)", [[0, True, 1, False, 2, True]], b"\x00\x01\x01\x00\x02\x01"),
		("B /0(B)", [3, [0, 1, 2]], b"\x03\x00\x01\x02"),
		("B /p1(B)", [3, [0, 1, 2]], b"\x03\x00\x01\x02"),
		("B (B /0(B))", [0xFF, [3, [0, 1, 2]]], b"\xFF\x03\x00\x01\x02"),
		("B (B /p1(B))", [0xFF, [3, [0, 1, 2]]], b"\xFF\x03\x00\x01\x02"),
		("B (2B) /0B", [3, [0xFF, 0xFF], 0, 1, 2], b"\x03\xFF\xFF\x00\x01\x02"),
		("B (2B) /p2B", [3, [0xFF, 0xFF], 0, 1, 2], b"\x03\xFF\xFF\x00\x01\x02"),
	]
	
	def test_group(self):
		for structure, unpacked, packed in self.group_cases:
			with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
				self.assertSequenceEqual(rawutil.unpack(structure, packed), unpacked)
				self.assertEqual(rawutil.pack(structure, *unpacked), packed)
	
	iterator_cases = [
		("2[2B]", [[[0, 1], [2, 3]]], b"\x00\x01\x02\x03"),
		("B 2[2B]", [0xFF, [[0, 1], [2, 3]]], b"\xFF\x00\x01\x02\x03"),
		("2[2B] B", [[[0, 1], [2, 3]], 0xFF], b"\x00\x01\x02\x03\xFF"),
		("B 2[2B] B", [0xFF, [[0, 1], [2, 3]], 0xFE], b"\xFF\x00\x01\x02\x03\xFE"),
		("B /0[2B]", [2, [[0, 1], [2, 3]]], b"\x02\x00\x01\x02\x03"),
		("B /p1[2B]", [2, [[0, 1], [2, 3]]], b"\x02\x00\x01\x02\x03"),
		("[2B]", [[[0, 1]]], b"\x00\x01"),
		("0[2B]", [[]], b""),
		("B /0[2B]", [0, []], b"\x00"),
		("2[B /0?]", [[[3, True, True, False], [2, False, True]]], b"\x03\x01\x01\x00\x02\x00\x01"),
		("2[B /p1?]", [[[3, True, True, False], [2, False, True]]], b"\x03\x01\x01\x00\x02\x00\x01"),
		("B /0(3[B/0s])", [2, [[[3, b"foo"], [3, b"bar"], [3, b"baz"]], [[4, b"spam"], [3, b"ham"], [3, b"egg"]]]], b"\x02\x03foo\x03bar\x03baz\x04spam\x03ham\x03egg"),
		("B {2B}", [0xFF, [[0, 1], [2, 3], [4, 5]]], b"\xFF\x00\x01\x02\x03\x04\x05"),
		("B 2[2B] /0B", [3, [[0xFF, 0xFF], [0x77, 0x77]], 0, 1, 2], b"\x03\xFF\xFF\x77\x77\x00\x01\x02"),
		("B 2[2B] /p2B", [3, [[0xFF, 0xFF], [0x77, 0x77]], 0, 1, 2], b"\x03\xFF\xFF\x77\x77\x00\x01\x02"),
	]
	
	def test_iterator(self):
		for structure, unpacked, packed in self.iterator_cases:
			with self.subTest(structure=structure, unpacked=unpacked, packed=packed):
				self.assertSequenceEqual(rawutil.unpack(structure, packed), unpacked)
				self.assertEqual(rawutil.pack(structure, *unpacked), packed)
	
	def test_substructure_reference_locality(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B (B /p2B)")
	
	def test_substructure_error_mixup(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B (B [B) B] B")
	
	def test_consumer_error_end(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B {2B} B")
	
	def test_consumer_error_multiple(self):
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B 2{2B}")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /0{2B}")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B /p1{2B}")
		with self.assertRaises(rawutil.FormatError):
			structobj = rawutil.Struct("B #0{2B}")
	
	calcsize_simple = {
		"b": 1, "B": 1, "h": 2, "H": 2, "u": 3, "U": 3,
		"i": 4, "I": 4, "l": 4, "L": 4, "q": 8, "Q": 8,
		"e": 2, "f": 4, "d": 8, "F": 16, "?": 1, "x": 1,
		"c": 1,
	}
	
	calcsize_complex = {
		"4s": 4, "5X": 5,
		"4(bBhHuUiIlLqQefdF?xc) 3a": 309,
		"3(HB)": 9, "I 4[3B|2B 8a]": 48,
	}
	
	calcsize_error = [
		"$", "IB$", "{2B}", "5U 4a (13B 5s) 4a {4I}",
		"n", "3n", "B /0B", "B /p1B", "B (B /0B)", "B (B /p1B)"
	]
	
	def test_calcsize_simple(self):
		for structure, size in self.calcsize_simple.items():
			for byteorder in rawutil.ENDIANNAMES:
				for count in ("0", "1", "", "4"):
					with self.subTest(structure=structure, byteorder=byteorder, count=count):
						result = size * (int(count) if len(count) > 0 else 1)
						self.assertEqual(rawutil.calcsize(byteorder + count + structure), result)
	
	def test_calcsize_complex(self):
		for structure, size in self.calcsize_complex.items():
			with self.subTest(structure=structure):
				self.assertEqual(rawutil.calcsize(structure), size)
	
	def test_calcsize_error(self):
		for structure in self.calcsize_error:
			with self.subTest(structure=structure):
				with self.assertRaises(rawutil.FormatError):
					result = rawutil.calcsize(structure)
	
	def test_calcsize_refdata(self):
		structure = "#0I #1(#2I) #3[#4I]"
		refdata = [2, 3, 5, 1, 0]
		self.assertEqual(rawutil.calcsize(structure, refdata=refdata), 68)
