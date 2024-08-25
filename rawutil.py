# -*- coding:utf-8 -*-
# MIT License
#
# Copyright (c) 2017-2024 Tyulis
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""rawutil, a lightweight Python module to make complex binary structures easy

This module aims at providing means to interact with structured binary data in a
similary way to the standard module `struct`, but with way more features

FORMAT STRINGS REFERENCE :
- Byte-order marks : must be the first character, indicates the byte-order
					 to use with that structure
	- `<` : little-endian (least significant byte first)
	- `>` : big-endian (most significant byte first)
	- `=` : system byte order
	- `@` : also system byte order (no system alignments contrary to struct)
	- `!` : network byte order (big endian)
- Format characters : denote some data to process, like `struct`
	- `?` : 8-bits boolean (any non-zero value is True, True is packed as 0x01)
	- `b` : signed 8-bits integer
	- `B` : unsigned 8-bits integer
	- `h` : signed 16-bits integer
	- `H` : unsigned 16-bits integer
	- `u` : signed 24-bits integer
	- `U` : unsigned 24-bits integer
	- `i`, `l` : signed 32-bits integer
	- `I`, `L` : unsigned 32-bits integer
	- `q` : signed 64-bits integer
	- `Q` : unsigned 64-bits integer
	- `e` : half-precision IEEE754 floating-point number (16-bits)
	- `f` : single-precision IEEE754 floating-point number (32-bits)
	- `d` : double-precision IEEE754 floating-point number (64-bits)
	- `F` : quadruple-precision IEEE754 floating-point number (128-bits)
	- `c` : single character (as a 1-byte `bytes` object)
	- `s` : string (length is given by the count, for instance `16s` is a
			16-bytes string), as a `bytes` object
	- `n` : null-terminated string (stops at the first null byte, null byte is
			not included). The count gives a number of strings, not the length
	- `X` : hexadecimal string, works like `s` but converts to hex
	- `x` : padding byte, packed as 0x00, not included in the unpacked data
	- `a` : alignment, pads with null bytes until the next multiple of the count
	- `|` : alignment reference, `a` formats align according to the beginning of
			the format or the previous `|` character
	- `$` : consumes all remaining data as a bytes object
- Counts : give an amount of successive elements of the same type, or sometimes
		   a length (e.g. 4I = IIII = 4 uint32, 16s = 16-bytes string)
	- ``	: no count is always equivalent to 1
	- `4`   : the count can be given directly as a number
	- `/1`  : absolute reference, the value of the n-th element of the structure
			  is used as the count (here if the second element is 3, this makes a
			  count of 3). Indices start at 0
	- `/p1` : relative reference, the value of the n-th previous element is used
			  as the count (e.g. /p1 is the immediately previous element, /p2 2
			  elements before, etc.). Indices start at 1, like with negative
			  indices
	- `#0`  : external reference, the count is given by the element at index n of
			  the parameter `refdata` given to rawutil functions
Substructures : extracted in sub-lists, allow to organise better and implement
				iteration directly in structures. References and alignments are
				always local to their substructure.
	- `5(2B i)` : group, the substructure is simply extracted into a sub-list.
				  If a count is given, it extracts the group n times but in the
				  same list (ex. `3(I)` makes [1, 2, 3]), this allows to use
				  references for list lengths (like in `I /0(n)`, this extracts
				  as much strings as given by the I but in a sub-list)
	- `5[2B i]` : iterator, the substructure is extracted as much times as given
				  by the count, each times in a separate sub-list (ex. 3[2I]
				  can give [[1, 2], [3, 4], [5, 6]])
	- `{2B i}`  : infinite iterator, works just like `[]` but continues until
				  there is no more data to read
"""

import io
import sys
import math
import copy
import collections

__version__ = "2.9.0"

ENDIANNAMES = {
	"=": sys.byteorder,
	"@": sys.byteorder,
	">": "big",
	"!": "big",
	"<": "little",
}

ENDIANMARKS = {
	"little": "<",
	"big": ">",
}


def padding_to_multiple(initial_size, alignment):
	"""Compute the padding to add to go from `initial_size` to the next multiple of `alignment`
	Ex. align 13 to the next multiple of 4 -> return 3 (13 + 3 = 16)"""
	return alignment - (initial_size % alignment or alignment)


class FormatError (Exception):
	pass


class OperationError (Exception):
	pass

class DataError (OperationError):
	pass

class ResolutionError (OperationError):
	pass


def _error_context(message, format, position):
	return f"{message}\n\tIn format '{format}', position {position}\n\t{'-' * (11 + position)}^"


class _Reference (object):
	__slots__ = ("type", "value")

	# The standard library enums are extremely slow for some reason, enough to double parsing times if reference types are an enum
	# Use namedtuples instead to keep it relatively fast and clean
	_ReferenceType = collections.namedtuple("_ReferenceType", ["name", "format"])

	Relative = _ReferenceType(name="Relative", format="/p")
	Absolute = _ReferenceType(name="Absolute", format="/")
	External = _ReferenceType(name="External", format="#")

	# Those must be checked in that order
	TYPES = (Relative, Absolute, External)

	def __init__(self, type, value):
		self.type = type
		self.value = value

	def __repr__(self):
		return f"{self.__class__.__name__}({self.type.name}, {self.value})"


class _Token (object):
	__slots__ = ("count", "type", "content", "position")

	def __init__(self, count, type, content, position):
		self.count = count
		self.type = type
		self.content = content
		self.position = position

	def __repr__(self):
		return f"{self.__class__.__name__}({self.count !r}, '{self.type}', {self.content !r}, {self.position !r})"

def _read(data, length=-1):
	readdata = data.read(length)
	if len(readdata) < length:
		raise IndexError("Not enough data to read")
	return readdata

def _list_identity(*elements):
	return list(elements)


_StructureCharacter = collections.namedtuple("_StructureCharacter", [
	"character",

	# Everything defaults to False or None
	"is_integer",         # True if it is a simple integer type
	"is_floating_point",  # True if it is a simple floating-point type
	"has_count",          # True if it accepts a count attribute
	"is_direct_count",    # True if the count is simply a repeat count (meaning the element corresponds to `count` items in the unpacked list), False if it is interpreted in another way
	"is_final",           # True if it terminates the structure
	"is_substructure",    # True if it introduces a substructure
	"is_control",         # True if it is a control character that does not correspond to any actual data
	"fixed_size",         # Fixed size of the type in bytes (-> 4<char> has size 4 * fixed_size), or None if it has no such fixed size
	
	# Defaults to True
	"has_output",         # True if it corresponds to a value in the unpacked list
	
	# Type-specific, with defaults
	"closing_character",  # For substructures : Corresponding closing character
	"is_signed",          # For integer types : True if it is a signed integer
	"nof_exponent_bits",  # For floating-point types : Number of exponent bits in the IEEE754 structure
	"nof_mantissa_bits",  # For floating-point types : Number of mantissa bits in the IEEE754 structure
	"exponent_bias",      # For floating-point types : Offset applied to the encoded exponent in the IEEE754 structure
], defaults=[None, False, False, False, False, False, False, None, True, None, False, None, None, None])

_STRUCTURE_CHARACTERS = {
	# Integer types
	"?": _StructureCharacter("?", has_count=True, is_direct_count=True, fixed_size=1),
	"b": _StructureCharacter("b", is_integer=True, has_count=True, is_direct_count=True, is_signed=True,  fixed_size=1),
	"B": _StructureCharacter("B", is_integer=True, has_count=True, is_direct_count=True, is_signed=False, fixed_size=1),
	"h": _StructureCharacter("h", is_integer=True, has_count=True, is_direct_count=True, is_signed=True,  fixed_size=2),
	"H": _StructureCharacter("H", is_integer=True, has_count=True, is_direct_count=True, is_signed=False, fixed_size=2),
	"u": _StructureCharacter("u", is_integer=True, has_count=True, is_direct_count=True, is_signed=True,  fixed_size=3),
	"U": _StructureCharacter("U", is_integer=True, has_count=True, is_direct_count=True, is_signed=False, fixed_size=3),
	"i": _StructureCharacter("i", is_integer=True, has_count=True, is_direct_count=True, is_signed=True,  fixed_size=4),
	"I": _StructureCharacter("I", is_integer=True, has_count=True, is_direct_count=True, is_signed=False, fixed_size=4),
	"l": _StructureCharacter("l", is_integer=True, has_count=True, is_direct_count=True, is_signed=True,  fixed_size=4),
	"L": _StructureCharacter("L", is_integer=True, has_count=True, is_direct_count=True, is_signed=False, fixed_size=4),
	"q": _StructureCharacter("q", is_integer=True, has_count=True, is_direct_count=True, is_signed=True,  fixed_size=8),
	"Q": _StructureCharacter("Q", is_integer=True, has_count=True, is_direct_count=True, is_signed=False, fixed_size=8),

	# Floating-point types
	"e": _StructureCharacter("e", is_floating_point=True, has_count=True, is_direct_count=True, fixed_size= 2, is_signed=True, nof_exponent_bits= 5, nof_mantissa_bits= 10, exponent_bias=   15),
	"f": _StructureCharacter("f", is_floating_point=True, has_count=True, is_direct_count=True, fixed_size= 4, is_signed=True, nof_exponent_bits= 8, nof_mantissa_bits= 23, exponent_bias=  127),
	"d": _StructureCharacter("d", is_floating_point=True, has_count=True, is_direct_count=True, fixed_size= 8, is_signed=True, nof_exponent_bits=11, nof_mantissa_bits= 52, exponent_bias= 1023),
	"F": _StructureCharacter("F", is_floating_point=True, has_count=True, is_direct_count=True, fixed_size=16, is_signed=True, nof_exponent_bits=15, nof_mantissa_bits=112, exponent_bias=16383),

	# Character types
	"c": _StructureCharacter("c", has_count=True, is_direct_count=True,  fixed_size=1),
	"s": _StructureCharacter("s", has_count=True, is_direct_count=False, fixed_size=1),
	"X": _StructureCharacter("X", has_count=True, is_direct_count=False, fixed_size=1),
	"n": _StructureCharacter("n", has_count=True, is_direct_count=True,  fixed_size=None),
	"$": _StructureCharacter("$", has_count=False, is_final=True, fixed_size=None),

	# Padding and alignment
	"x": _StructureCharacter("x", has_count=True, is_direct_count=True, has_output=False, fixed_size=1),
	"a": _StructureCharacter("a", has_count=True, is_direct_count=False, has_output=False, fixed_size=None),
	"|": _StructureCharacter("|", has_count=False, is_control=True, has_output=False, fixed_size=0),

	# Substructures
	"(": _StructureCharacter("(", is_substructure=True, has_count=True, is_direct_count=False, closing_character=")"),
	"[": _StructureCharacter("[", is_substructure=True, has_count=True, is_direct_count=False, closing_character="]"),
	"{": _StructureCharacter("{", is_substructure=True, has_count=False, is_final=True, closing_character="}"),
}


class Struct (object):
	"""Object that denotes a binary structure
	A Struct compiles a format once and for all, significantly
	improving performance for reused structures compared to standalone
	functions"""

	__slots__ = ("format", "tokens", "byteorder", "names", "forcebyteorder")

	def __init__(self, format="", names=None, *, safe_references=True):
		"""Setup the structure and compile the format

		- format : can be a format string to compile, or another Struct to copy
		- names : names for each element of data unpacked by this structure.
		          This can be a list of names, a string with space-separated
				  field names, or a callable that takes each field in order as
				  arguments (for instance a `namedtuple` type or a `dataclass`)
				  
		Keyword-only arguments :
		- safe_references : When set to False, allows "unsafe" behaviours, like
		          referencing an item inside or possibly beyond an indeterminate
				  amount of elements. Defaults to True (fail when encountering
				  those circumstances)
		"""

		self.names = None
		if isinstance(format, Struct):
			self.format = format.format
			self.byteorder = format.byteorder
			self.forcebyteorder = format.forcebyteorder
			self.tokens = copy.deepcopy(format.tokens)
			self.names = format.names
		elif len(format) > 0:
			self.format = format
			self.byteorder = sys.byteorder
			self.forcebyteorder = False
			self._parse_struct(format, safe_references)
		else:
			self.format = format
			self.byteorder = sys.byteorder
			self.forcebyteorder = False
			self.tokens = []

		self.names = self._build_result_converter(names)

	def setbyteorder(self, byteorder):
		if byteorder in ENDIANNAMES:
			byteorder = ENDIANNAMES[byteorder]
		self.forcebyteorder = True
		self.byteorder = byteorder

	def unpack(self, data, names=None, refdata=(), byteorder=None):
		"""Unpack data from the given source according to this structure

		- data : any bytes-like or binary readable file-like object, all data
		        is read from it. If it is a file-like object, reading starts
				from its current position and leaves it after the data that
				has been read
		- names : names for each element of data unpacked by this structure.
		        This can be a list of names, a string with space-separated
				field names, or a callable that takes each field in order as
				arguments (for instance a `namedtuple` type or a `dataclass`)
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[0] as a count)
		- byteorder : Force the byte order for this action only ("little" / "big")
		"""

		if byteorder is None:
			byteorder = self.byteorder

		if hasattr(data, "read") and hasattr(data, "tell"):  # From file-like object
			unpacked = self._unpack_file(data, self.tokens, refdata, byteorder)
		else:  # From bytes-like objet
			unpacked = self._unpack_file(io.BytesIO(data), self.tokens, refdata, byteorder)

		result_converter = self._build_result_converter(names)
		return result_converter(*unpacked)

	def unpack_from(self, data, offset=None, names=None, refdata=(), getptr=False, byteorder=None):
		"""Unpack data from the given source at the given position

		- data : any bytes-like or binary readable file-like object, all data
		        is read from it. If it is a file-like object, reading starts
				from the given absolute position and leaves it after the data
				that has been read
		- offset : Absolute position in the data or file to start reading from.
		        Defaults to 0 for bytes-like objects or the current position for
				file-like objects
		- names : names for each element of data unpacked by this structure.
		        This can be a list of names, a string with space-separated
				field names, or a callable that takes each field in order as
				arguments (for instance a `namedtuple` type or a `dataclass`)
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		- getptr : If set to True, also returns the position immediately after
		        the unpacked data
		- byteorder : Force the byte order for this action only ("little" / "big")
		"""

		if byteorder is None:
			byteorder = self.byteorder

		if hasattr(data, "read") and hasattr(data, "tell"):  # From file-like object
			if offset is not None:
				data.seek(offset)
			unpacked = self._unpack_file(data, self.tokens, refdata, byteorder)
		else:  # From bytes-like objet
			data = io.BytesIO(data)
			if offset is not None:
				data.seek(offset)
			unpacked = self._unpack_file(data, self.tokens, refdata, byteorder)

		result_converter = self._build_result_converter(names)
		unpacked = result_converter(*unpacked)

		if getptr:
			return unpacked, data.tell()
		else:
			return unpacked

	def pack(self, *data, refdata=(), byteorder=None):
		"""Pack data as bytes according to this structure

		- data : all elements to pack, in order
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		- byteorder : Force the byte order for this action only ("little" / "big")
		"""
		if byteorder is None:
			byteorder = self.byteorder

		data = list(data)

		out = io.BytesIO()
		self._pack_file(out, data, refdata, byteorder)
		out.seek(0)
		return out.read()

	def pack_into(self, buffer, offset, *data, refdata=(), byteorder=None):
		"""Pack data into an existing buffer at the given position

		- buffer : writable bytes-like object (e.g. a bytearray), where the data
		        will be written
		- offset : position in the buffer to start writing from
		- data : all elements to pack, in order
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		- byteorder : Force the byte order for this action only ("little" / "big")
		"""
		if byteorder is None:
			byteorder = self.byteorder

		out = io.BytesIO()
		self._pack_file(out, data, refdata, byteorder)
		out.seek(0)
		packed = out.read()
		buffer[offset: offset + len(packed)] = packed

	def pack_file(self, file, *data, position=None, refdata=(), byteorder=None):
		"""Pack data into a file-like object

		- file : writable binary file-like object, where the data will be
		        written. It is left after the data that has been written
		- data : all elements to pack, in order
		- position : absolute position in the file to start writing from.
		        Defaults to the current position
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		- byteorder : Force the byte order for this action only ("little" / "big")
		"""
		if byteorder is None:
			byteorder = self.byteorder

		if position is not None:
			file.seek(position)
		self._pack_file(file, data, refdata, byteorder)

	def iter_unpack(self, data, names=None, refdata=(), byteorder=None):
		"""Create an iterator that successively unpacks according to this
		structure at each iteration

		- data : any bytes-like or binary readable file-like object, all data
		        is read from it. If it is a file-like object, reading starts
				from its current position and leaves it after the data that
				has been read
		- names : names for each element of data unpacked by this structure.
		        This can be a list of names, a string with space-separated
				field names, or a callable that takes each field in order as
				arguments (for instance a `namedtuple` type or a `dataclass`)
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[0] as a count)
		- byteorder : Force the byte order for this action only ("little" / "big")
		"""
		if byteorder is None:
			byteorder = self.byteorder

		if hasattr(data, "read") and hasattr(data, "seek") and hasattr(data, "tell"):  # From file-like object
			buffer = data
			pos = buffer.tell()
			buffer.seek(0, 2)
			end = buffer.tell()
			buffer.seek(pos)
		else:
			buffer = io.BytesIO(data)
			end = len(data)

		result_converter = self._build_result_converter(names)
		while buffer.tell() < end:
			unpacked = self._unpack_file(buffer, self.tokens, refdata, byteorder)
			yield result_converter(*unpacked)

	def calcsize(self, refdata=None):
		"""Calculate the size in bytes of the data represented by this structure

		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		When the size is indeterminate (elements that require actual data as
		context, like null-terminated strings, internal references, …), fail
		with a FormatError
		"""
		return self._calcsize_out_of_context(self.tokens, refdata)

	def packed_size(self, *data, refdata=None):
		"""Calculate in-context the size in bytes of the packed `data`
		This acts like `calcsize` but in the context of the given `data`,
		allowing to calculate the size of variable-size structures
		
		- data : data that would be packed
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)"""
		nof_elements_packed, total_size = self._calcsize_in_context(data, self.tokens, refdata)
		return total_size

	def _parse_struct(self, format, safe_references=True):
		format = format.strip()
		if format[0] in tuple(ENDIANNAMES.keys()):
			self.byteorder = ENDIANNAMES[format[0]]
			self.forcebyteorder = True
			format = format[1:]
			startpos = 1
		else:
			startpos = 0

		self.tokens = self._parse_substructure(format, safe_references, startpos)
	
	def _parse_substructure(self, format, safe_references, report_start_position):
		"""Recursively parse `format`. `report_start_position` is the start position of `format` in the top-level format string, for use in error reports"""
		tokens = []
		position = 0                           # Current position in `format`
		has_uncountable_interruption = False   # Whether uncountable elements have been found already
		nof_forwards_countable_elements = 0    # Maximum absolute reference index (number of consecutive countable elements at the beginning)
		nof_backwards_countable_elements = 0   # Maximum relative reference index (number of consecutive countable elements last encountered)
		format_length = len(format)
	
		while position < format_length:
			# Skip whitespace and comments
			if format[position].isspace():
				position += 1
				continue
			elif format[position] in ["'", '"']:
				next_quote_position = format.find(format[position], position + 1)
				if next_quote_position < 0:
					raise FormatError(_error_context("Unterminated comment", self.format, report_start_position + position))
				position = next_quote_position + 1
				continue
			
			element_start_position = position

			# Parse references
			for reference_type in _Reference.TYPES:
				if format.startswith(reference_type.format, position):
					position += len(reference_type.format)
					break
			else:
				reference_type = None
						
			count_start = position
			while format[position].isdigit():
				position += 1

			# Found a count value
			if position > count_start:
				count = int(format[count_start:position])
				if reference_type is not None:
					if reference_type == _Reference.Absolute:
						if not has_uncountable_interruption and count >= nof_forwards_countable_elements:
							raise FormatError(_error_context("Invalid reference index : absolute reference unambiguously points at itself or elements located after itself", self.format, report_start_position + element_start_position))
						elif safe_references and count >= nof_forwards_countable_elements:
							raise FormatError(_error_context("Unsafe reference index : absolute reference points in or after an indeterminate amount of elements (typically a reference). If it is intended, use the parameter safe_references=False of the Struct() constructor", self.format, report_start_position + element_start_position))
					if reference_type == _Reference.Relative:
						if count <= 0:
							raise FormatError(_error_context("Invalid reference index : relative reference points at itself (the immediate previous element is /p1)", self.format, report_start_position + element_start_position))
						elif not has_uncountable_interruption and count > nof_forwards_countable_elements:
							raise FormatError(_error_context("Invalid reference index : relative reference unambiguously points beyond the beginning of the format", self.format, report_start_position + element_start_position))
						elif safe_references and count > nof_backwards_countable_elements:
							raise FormatError(_error_context("Unsafe reference index : relative reference points in or beyond an indeterminate amount of elements (typically a reference). If it is intended, use the parameter safe_references=False of the Struct() constructor", self.format, report_start_position + element_start_position))
					count = _Reference(reference_type, count)

			# No count value, assume 1
			else:
				if reference_type is not None:
					raise FormatError(_error_context("Reference without index", self.format, report_start_position + element_start_position))
				count = 1

			if format[position] not in _STRUCTURE_CHARACTERS:
				raise FormatError(_error_context(f"Unrecognised format character '{format[position]}'", self.format, report_start_position + element_start_position))
			character = _STRUCTURE_CHARACTERS[format[position]]
			position += 1

			if count != 1 and not character.has_count:
				raise FormatError(_error_context(f"Format character '{character.character}' cannot have a count", self.format, report_start_position + element_start_position))

			# Parse substructure
			if character.is_substructure:
				substructure_start = position
				
				nesting_level = 1
				while nesting_level > 0:
					next_closing = format.find(character.closing_character, position)
					if next_closing < 0:  # No closing character remaining -> unterminated
						raise FormatError(_error_context("Unterminated substructure", self.format, report_start_position + element_start_position))
					
					next_opening = format.find(character.character, position)
					if next_opening >= 0 and next_opening < next_closing:  # Next opening character before closing character
						position = next_opening + 1
						nesting_level += 1
					else:  # Next closing character before opening character
						position = next_closing + 1
						nesting_level -= 1
				
				substructure = format[substructure_start:position - 1]
				content = self._parse_substructure(substructure, safe_references, report_start_position + substructure_start)
				nof_elements = 1
			
			# Parse normal structure elements
			else:
				content = None
				if character.is_control:
					nof_elements = 0
				elif character.is_direct_count:
					if isinstance(count, _Reference):
						nof_elements = None
					else:
						nof_elements = count
				else:
					nof_elements = 1


			if position < format_length and character.is_final:
				raise FormatError(_error_context(f"'{character.character}' terminates the structure, there should be nothing else afterwards", self.format, report_start_position + element_start_position))

			# Slight optimization for pack and unpack : reduce things like IIII -> 4I
			if character.is_direct_count and len(tokens) > 0 and character.character == tokens[-1].type and not isinstance(count, _Reference) and not isinstance(tokens[-1].count, _Reference):
				tokens[-1].count += count
			else:
				token = _Token(count, character.character, content, element_start_position)
				tokens.append(token)
				
			# Check for countable / uncountable elements
			if nof_elements is None:  # Uncountable
				nof_backwards_countable_elements = 0
				has_uncountable_interruption = True
			else:
				nof_backwards_countable_elements += nof_elements
				if not has_uncountable_interruption:
					nof_forwards_countable_elements += nof_elements
		
		return tokens

	def _build_result_converter(self, names):
		# If not callable, make it a namedtuple
		if names is None:
			if self.names is None:
				return _list_identity
			else:
				return self.names
		elif hasattr(names, "__call__"):
			return names
		else:
			return collections.namedtuple("RawutilNameSpace", names)

	def _resolve_count(self, token, unpacked, refdata):
		if isinstance(token.count, _Reference):
			try:
				if token.count.type == _Reference.Relative:
					value = unpacked[-token.count.value]
				elif token.count.type == _Reference.Absolute:
					value = unpacked[token.count.value]
				elif token.count.type == _Reference.External:
					value = refdata[token.count.value]
				
				return value.__index__()
			except AttributeError as exc:
				raise TypeError(_error_context(f"Count from {token.count.type.name} reference index {token.count.value} must be an integer", self.format, token.position)) from exc
			except IndexError as exc:
				raise ResolutionError(_error_context(f"Invalid {token.count.type.name} reference index : {token.count.value}", self.format, token.position)) from exc
		else:
			return token.count

	def _decode_float(self, data, exponentsize, mantissasize, byteorder):
		maxed_exponent = (1 << exponentsize) - 1

		encoded = int.from_bytes(data, byteorder=byteorder, signed=False)
		base_exponent = (encoded >> mantissasize) & maxed_exponent
		mantissa = encoded & ((1 << mantissasize) - 1)
		sign = -1 if (encoded >> (exponentsize + mantissasize)) else 1

		if base_exponent == 0:
			# Exponent 0, mantissa = 0 -> zero
			if mantissa == 0:
				return sign * 0.0
			# Exponent 0, mantissa ≠ 0 -> subnormal
			else:
				exponent = 2 - (1 << (exponentsize - 1))
				denormalized = mantissa / 2**mantissasize
				return sign * denormalized * 2**exponent
		elif base_exponent == maxed_exponent:
			# Maxed exponent, mantissa = 0 -> infinity
			if mantissa == 0:
				return sign * math.inf
			# Maxed exponent, mantissa ≠ 0 -> NaN
			else:
				return math.nan
		# Otherwise, normal number
		else:
			exponent = base_exponent - ((1 << (exponentsize - 1)) - 1)
			normalized = 1 + mantissa / 2**mantissasize
			return sign * normalized * 2**exponent

	def _build_float(self, token, value, exponentsize, mantissasize):
		maxed_exponent = (1 << exponentsize) - 1
		size = 1 + exponentsize + mantissasize
		sign = 0 if value >= 0 else 1
		value = abs(value)

		if value == 0:
			exponent = 0
			mantissa = 0
		elif value == math.inf:
			exponent = maxed_exponent
			mantissa = 0
		elif math.isnan(value):  # Here, NaN is packed in the same way `struct` does
			exponent = maxed_exponent
			mantissa = 1 << (mantissasize - 1)
			sign = 0
		else:
			normalized, biased_exponent = math.frexp(value)

			# frexp returns the mantissa between 0.5 and 1, we want it between 1 and 2
			normalized *= 2
			biased_exponent -= 1

			min_biased_exponent = 2 - (1 << (exponentsize - 1))
			max_biased_exponent = (1 << (exponentsize - 1)) - 1

			if biased_exponent > max_biased_exponent:
				raise OverflowError(_error_context(f"Floating-point value {value} is too big for {size * 8} bits float", self.format, token.position))
			elif biased_exponent < min_biased_exponent:  # Too small -> subnormal
				exponent = 0
				normalized = value / 2**min_biased_exponent
			else:  # Normal number -> strip the trivial 1
				exponent = biased_exponent + max_biased_exponent
				normalized -= 1
			
			mantissa = normalized * (1 << mantissasize)
			rounded_mantissa = int(mantissa)
			remainder = mantissa - rounded_mantissa
			# Staying with struct, round to the nearest, ties to even
			if 0.5 < remainder < 1 or (remainder == 0.5 and rounded_mantissa & 1):
				rounded_mantissa += 1
				# On the upper edge of the value range, it is possible that the
				# rounding made the value overflow without being detected earlier
				if rounded_mantissa >= (1 << mantissasize):
					raise OverflowError(_error_context(f"Floating-point value {value} is too big for {size * 8} bits float", self.format, token.position))
			mantissa = rounded_mantissa
		return sign, exponent, mantissa


	def _unpack_file(self, data, tokens, refdata, byteorder):
		alignref = data.tell()
		unpacked = []

		for token in tokens:
			count = self._resolve_count(token, unpacked, refdata)
			character = _STRUCTURE_CHARACTERS[token.type]

			try:
				# Groups
				if token.type == "(":
					multigroup = []
					for i in range(count):
						subgroup = self._unpack_file(data, token.content, refdata, byteorder)
						multigroup.extend(subgroup)
					unpacked.append(multigroup)
				elif token.type == "[":
					sublist = []
					for i in range(count):
						subgroup = self._unpack_file(data, token.content, refdata, byteorder)
						sublist.append(subgroup)
					unpacked.append(sublist)
				elif token.type == "{":
					sublist = []
					while True:
						try:
							subgroup = self._unpack_file(data, token.content, refdata, byteorder)
						except DataError:
							break
						sublist.append(subgroup)
					unpacked.append(sublist)
				# Control
				elif token.type == "|":
					alignref = data.tell()
				elif token.type == "a":
					padding = padding_to_multiple(data.tell() - alignref, count)
					data.seek(padding, 1)
				elif token.type == "$":
					unpacked.append(_read(data))
				# Elements
				elif character.is_integer:
					groupdata = _read(data, character.fixed_size * count)
					for i in range(count):
						unpacked.append(int.from_bytes(groupdata[i*character.fixed_size: (i+1)*character.fixed_size], byteorder=byteorder, signed=character.is_signed))
				elif character.is_floating_point:
					groupdata = _read(data, character.fixed_size * count)
					for i in range(count):
						elementdata = groupdata[i*character.fixed_size: (i+1)*character.fixed_size]
						decoded = self._decode_float(elementdata, character.nof_exponent_bits, character.nof_mantissa_bits, byteorder)
						unpacked.append(decoded)
				elif token.type == "x":
					data.seek(count, 1)
				elif token.type == "?":
					elementdata = _read(data, count)
					unpacked.extend([bool(byte) for byte in elementdata])
				elif token.type == "c":
					elementdata = _read(data, count)
					unpacked.extend([bytes((byte, )) for byte in elementdata])
				elif token.type == "s":
					unpacked.append(_read(data, count))
				elif token.type == "n":
					for _ in range(count):
						string = b""
						while True:
							char = _read(data, 1)
							if char == b"\x00":
								break
							else:
								string += char
						unpacked.append(string)
				elif token.type == "X":
					elementdata = _read(data, count)
					unpacked.append(elementdata.hex())
			except IndexError:
				raise DataError(_error_context(f"No data remaining to read element '{token.type}'", self.format, token.position))

		return unpacked

	def _pack_file(self, out, data, refdata, byteorder, tokens=None):
		if tokens is None:
			tokens = self.tokens
		position = 0
		alignref = out.tell()
		for token in tokens:
			count = self._resolve_count(token, data[:position], refdata)
			character = _STRUCTURE_CHARACTERS[token.type]
			try:
				# Groups
				if token.type == "(":
					grouppos = 0
					for _ in range(count):
						grouppos += self._pack_file(out, data[position][grouppos:], refdata, byteorder, token.content)
					position += 1
				elif token.type == "[":
					for _, group in zip(range(count), data[position]):
						self._pack_file(out, group, refdata, byteorder, token.content)
					position += 1
				elif token.type == "{":
					for group in data[position]:
						self._pack_file(out, group, refdata, byteorder, token.content)
					position += 1
				# Control
				elif token.type == "|":
					alignref = out.tell()
				elif token.type == "a":
					padding = padding_to_multiple(out.tell() - alignref, count)
					out.write(b"\x00" * padding)
				elif token.type == "$":
					out.write(data[position])
					position += 1
				elif character.is_integer:
					elementdata = b""
					try:
						for _ in range(count):
							elementdata += data[position].to_bytes(character.fixed_size, byteorder=byteorder, signed=character.is_signed)
							position += 1
					except AttributeError as exc:
						raise TypeError(_error_context(f"Wrong type for format '{token.type}', the given object must be an integer or have a .to_bytes() method similar to int", self.format, token.position))
					out.write(elementdata)
				elif character.is_floating_point:
					elementdata = b""
					for _ in range(count):
						decoded = data[position]
						position += 1

						sign, exponent, mantissa = self._build_float(token, decoded, character.nof_exponent_bits, character.nof_mantissa_bits)
						encoded = (((sign << character.nof_exponent_bits) | exponent) << character.nof_mantissa_bits) | mantissa
						elementdata += encoded.to_bytes(character.fixed_size, byteorder=byteorder, signed=False)
					out.write(elementdata)
				elif token.type == "x":
					out.write(b"\x00" * count)
				elif token.type == "?":
					elementdata = bytes(data[position: position + count])
					out.write(elementdata)
					position += count
				elif token.type == "c":
					elementdata = b"".join(data[position: position + count])
					out.write(elementdata)
					position += count
				elif token.type == "s":
					string = self._encode_string(data[position])
					if len(string) != count:
						raise OperationError(_error_context(f"Length of structure element 's' {count} and data '{data[position] !r}' do not match", self.format, token.position))
					out.write(string)
					position += 1
				elif token.type == "n":
					for _ in range(count):
						string = self._encode_string(data[position])
						out.write(string + b"\x00")
						position += 1
				elif token.type == "X":
					out.write(bytes.fromhex(data[position]))
					position += 1
			except IndexError:
				raise DataError(_error_context(f"No data remaining to pack into element '{token.type}'", self.format, token.position))
		return position
	
	def _calcsize_out_of_context(self, tokens, refdata=None):
		total_size = 0
		alignment_reference = 0
		for token in tokens:
			character = _STRUCTURE_CHARACTERS[token.type]

			if isinstance(token.count, _Reference):
				if token.count.type == _Reference.External and refdata is not None:
					count = refdata[token.count.value]
				else:
					raise FormatError(_error_context("Impossible to compute the size of a structure with references", self.format, token.position))
			else:
				count = token.count

			if character.is_final:
				raise FormatError(_error_context(f"Impossible to compute the size of a structure with finalizing character {token.type}", self.format, token.position))
			elif character.is_substructure:
				total_size += count * self._calcsize_out_of_context(token.content, refdata)
			elif token.type == "|":
				alignment_reference = total_size
			elif token.type == "a":
				total_size += padding_to_multiple(total_size - alignment_reference, count)
			elif character.fixed_size is not None:
				total_size += count * character.fixed_size
			else:
				raise FormatError(_error_context(f"Impossible to compute the size of a structure with '{token.type}' elements", self.format, token.position))
					
		return total_size

	def _calcsize_in_context(self, data, tokens, refdata=None):
		position = 0
		total_size = 0
		alignment_reference = 0

		for token in tokens:
			count = self._resolve_count(token, data[:position], refdata)
			character = _STRUCTURE_CHARACTERS[token.type]
			try:
				# Substructures
				if token.type == "(":
					group_position = 0
					for _ in range(count):
						nof_elements_packed, group_size = self._calcsize_in_context(data[position][group_position:], token.content, refdata)
						group_position += nof_elements_packed
						total_size += group_size
					position += 1
				elif token.type == "[":
					for _, group in zip(range(count), data[position]):
						nof_elements_packed, group_size = self._calcsize_in_context(group, token.content, refdata)
						total_size += group_size
					position += 1
				elif token.type == "{":
					for group in data[position]:
						nof_elements_packed, group_size = self._calcsize_in_context(group, token.content, refdata)
						total_size += group_size
					position += 1
				
				# Control
				elif token.type == "|":
					alignment_reference = total_size
				elif token.type == "a":
					total_size += padding_to_multiple(total_size - alignment_reference, count)
				elif token.type == "$":
					total_size += len(data[position])
					position += 1
				elif character.fixed_size is not None:
					total_size += count * character.fixed_size
					if character.has_output:
						if character.is_direct_count:
							position += count
						else:
							position += 1
				elif token.type == "n":
					for _ in range(count):
						string = self._encode_string(data[position])
						total_size += len(string) + 1
						position += 1
			except IndexError:
				raise DataError(_error_context(f"No data remaining to pack into element '{token.type}'", self.format, token.position))
		return position, total_size



	def _encode_string(self, data):
		try:
			string = data.encode("utf-8")
		except (AttributeError, UnicodeDecodeError):
			string = data
		return string

	def _count_to_format(self, count):
		if count == 1:
			return ""
		elif isinstance(count, _Reference):
			return count.type.format + str(count.value)
		else:
			return str(count)

	def _tokens_to_format(self, tokens):
		format = ""
		for token in tokens:
			character = _STRUCTURE_CHARACTERS[token.type]
			if character.is_substructure:
				subformat = self._tokens_to_format(token.content)
				format += self._count_to_format(token.count) + token.type + subformat + character.closing_character + " "
			else:
				format += self._count_to_format(token.count) + token.type + " "
		return format.strip()

	def _max_external_reference(self, tokens):
		maxref = -1
		for token in tokens:
			if isinstance(token.count, _Reference):
				if token.count.type == _Reference.External:
					if token.count.value > maxref:
						maxref = token.count.value
			if token.content is not None:
				submax = self._max_external_reference(token.content)
				if submax > maxref:
					maxref = submax
		return maxref

	def _fix_external_references(self, tokens, leftexternals):
		for token in tokens:
			if isinstance(token.count, _Reference):
				if token.count.type == _Reference.External:
					token.count.value += leftexternals
			if token.content is not None:
				self._fix_external_references(token.content, leftexternals)
	
	def _token_element_count(self, token):
		"""Get the number of elements the given token actually represents, or None if it is uncountable (typically a reference)"""
		character = _STRUCTURE_CHARACTERS[token.type]
		
		if character.is_control is None:
			return 0
		elif character.is_direct_count:
			if isinstance(token.count, _Reference):
				return None
			else:
				return token.count
		else:
			return 1

	def _add_structs(self, lefttokens, righttokens):
		leftexternals = self._max_external_reference(lefttokens) + 1
		right_has_references = any(isinstance(token.count, _Reference) and token.count.type == _Reference.Absolute for token in righttokens)

		outtokens = []
		leftsize = 0
		for token in lefttokens:
			if token.type in ("{", "$"):
				raise FormatError("'" + token.type + ("}" if token.type == "{" else "") + "' forces the end of the structure, you can’t add or multiply structures if it causes those elements to be in the middle of the resulting structure")
			elif right_has_references and isinstance(token.count, _Reference) and _STRUCTURE_CHARACTERS[token.type].is_direct_count:
				raise FormatError("The left operand has an indeterminate amount of elements, impossible to fix right side absolute references")
			outtokens.append(copy.deepcopy(token))

			if leftsize is not None:
				nof_elements = self._token_element_count(token)
				if nof_elements is None:
					leftsize = None
				else:
					leftsize += nof_elements
				
		for token in righttokens:
			newtoken = copy.deepcopy(token)
			if isinstance(newtoken.count, _Reference):
				if newtoken.count.type == _Reference.Absolute:
					if leftsize is None:
						raise FormatError("The left operand has an indeterminate amount of elements, impossible to fix right side absolute references")
					newtoken.count.value += leftsize
				elif newtoken.count.type == _Reference.External:
					newtoken.count.value += leftexternals
			if newtoken.content is not None:
				self._fix_external_references(newtoken.content, leftexternals)
			outtokens.append(newtoken)
		outformat = self._tokens_to_format(outtokens)
		return outtokens, outformat

	def _multiply_struct(self, tokens, num):
		blocksize = 0
		for token in tokens:
			if blocksize is not None:
				nof_elements = self._token_element_count(token)
				if nof_elements is None:
					blocksize = None
				else:
					blocksize += nof_elements
			else:
				break

		blockexternals = self._max_external_reference(tokens) + 1
		if num > 1 and blocksize is None:
			raise FormatError("The multiplied structure contains an indeterminate amount of elements, impossible to fix absolute references")

		size = 0
		externals = 0
		outtokens = []
		for _ in range(num):
			for token in tokens:
				if token.type in ("{", "$"):
					raise FormatError("'" + token.type + ("}" if token.type == "{" else "") + "' forces the end of the structure, you can’t add or multiply structures if it causes those elements to be in the middle of the resulting structure")
				newtoken = copy.deepcopy(token)
				if isinstance(newtoken.count, _Reference):
					if newtoken.count.type == _Reference.Absolute:
						newtoken.count.value += size
					elif newtoken.count.type == _Reference.External:
						newtoken.count.value += externals
				if newtoken.content is not None:
					self._fix_external_references(newtoken.content, externals)
				outtokens.append(newtoken)
			size += blocksize
			externals += blockexternals
		outformat = self._tokens_to_format(outtokens)
		return outtokens, outformat


	def __add__(self, stct):
		if not isinstance(stct, Struct):
			stct = Struct(stct)
		newtokens, newformat = self._add_structs(self.tokens, stct.tokens)

		newstruct = Struct()
		newstruct.format = newformat
		newstruct.tokens = newtokens
		if self.forcebyteorder:
			newstruct.setbyteorder(self.byteorder)
		return newstruct

	def __iadd__(self, stct):
		if not isinstance(stct, Struct):
			stct = Struct(stct)
		newtokens, newformat = self._add_structs(self.tokens, stct.tokens)

		self.tokens = newtokens
		self.format = newformat
		return self

	def __radd__(self, stct):
		if not isinstance(stct, Struct):
			stct = Struct(stct)
		newtokens, newformat = self._add_structs(stct.tokens, self.tokens)

		newstruct = Struct()
		if stct.forcebyteorder:
			newstruct.setbyteorder(stct.byteorder)
		newstruct.tokens = newtokens
		newstruct.format = newformat
		return newstruct

	def __mul__(self, n):
		if n == 0:
			return Struct("")
		elif n == 1:
			return Struct(self)

		newtokens, newformat = self._multiply_struct(self.tokens, n)

		newstruct = Struct()
		if self.forcebyteorder:
			newstruct.setbyteorder(self.byteorder)
		newstruct.tokens = newtokens
		newstruct.format = newformat
		return newstruct

	def __imul__(self, n):
		if n == 0:
			self.format = ""
			self.tokens = []
		elif n > 1:
			newtokens, newformat = self._multiply_struct(self.tokens, n)
			self.tokens = newtokens
			self.format = newformat
		return self

	def __rmul__(self, n):
		if n == 0:
			return Struct("")
		elif n == 1:
			return Struct(self)

		newtokens, newformat = self._multiply_struct(self.tokens, n)
		newstruct = Struct()
		if self.forcebyteorder:
			newstruct.setbyteorder(self.byteorder)
		newstruct.tokens = newtokens
		newstruct.format = newformat
		return newstruct

	def __repr__(self):
		return "Struct(\"" + self.format + "\")"

	def __str__(self):
		return self.__repr__()


def unpack(structure, data, names=None, refdata=()):
	"""Unpack data from the given source

	- structure : format string or Struct object
	- data : any bytes-like or binary readable file-like object, all data
			is read from it. If it is a file-like object, reading starts
			from its current position and leaves it after the data that
			has been read
	- names : names for each element of data unpacked by this structure.
			This can be a list of names, a string with space-separated
			field names, or a callable that takes each field in order as
			arguments (for instance a `namedtuple` type or a `dataclass`)
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[0] as a count)
	"""
	stct = Struct(structure)
	return stct.unpack(data, names, refdata)

def unpack_from(structure, data, offset=None, names=None, refdata=(), getptr=False):
	"""Unpack data from the given source at the given position

	- structure : format string or Struct object
	- data : any bytes-like or binary readable file-like object, all data
			is read from it. If it is a file-like object, reading starts
			from the given absolute position and leaves it after the data
			that has been read
	- offset : Absolute position in the data or file to start reading from.
			Defaults to 0 for bytes-like objects or the current position for
			file-like objects
	- names : names for each element of data unpacked by this structure.
			This can be a list of names, a string with space-separated
			field names, or a callable that takes each field in order as
			arguments (for instance a `namedtuple` type or a `dataclass`)
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[1] as a count)
	- getptr : If set to True, also returns the position immediately after
			the unpacked data
	"""
	stct = Struct(structure)
	return stct.unpack_from(data, offset, names, refdata, getptr)

def iter_unpack(structure, data, names=None, refdata=()):
	"""Create an iterator that successively unpacks according to the
	structure at each iteration

	- structure : format string or Struct object
	- data : any bytes-like or binary readable file-like object, all data
			is read from it. If it is a file-like object, reading starts
			from its current position and leaves it after the data that
			has been read
	- names : names for each element of data unpacked by this structure.
			This can be a list of names, a string with space-separated
			field names, or a callable that takes each field in order as
			arguments (for instance a `namedtuple` type or a `dataclass`)
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[0] as a count)
	"""
	stct = Struct(structure)
	return stct.iter_unpack(data, names, refdata)

def pack(structure, *data, refdata=()):
	"""Pack data as bytes according to this structure

	- structure : format string or Struct object
	- data : all elements to pack, in order
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[1] as a count)
	"""
	stct = Struct(structure)
	return stct.pack(*data, refdata=refdata)

def pack_into(structure, buffer, offset, *data, refdata=()):
	"""Pack data into an existing buffer at the given position

	- structure : format string or Struct object
	- buffer : writable bytes-like object (e.g. a bytearray), where the data
			will be written
	- offset : position in the buffer to start writing from
	- data : all elements to pack, in order
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[1] as a count)
	"""
	stct = Struct(structure)
	return stct.pack_into(buffer, offset, *data, refdata=refdata)

def pack_file(structure, file, *data, position=None, refdata=()):
	"""Pack data into a file-like object

	- structure : format string or Struct object
	- file : writable binary file-like object, where the data will be
			written. It is left after the data that has been written
	- data : all elements to pack, in order
	- position : absolute position in the file to start writing from.
			Defaults to the current position
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[1] as a count)
	"""
	stct = Struct(structure)
	return stct.pack_file(file, *data, position=position, refdata=refdata)

def calcsize(structure, refdata=()):
	"""Calculate the size in bytes of the data represented by this structure

	- structure : format string or Struct object
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[1] as a count)
	When the size is indeterminate (elements that require actual data as
	context, like null-terminated strings, internal references, …), fail
	with a FormatError
	"""
	stct = Struct(structure)
	return stct.calcsize(refdata=refdata)

def packed_size(structure, *data, refdata=()):
	"""Calculate in-context the size in bytes of the packed `data`
	This acts like `calcsize` but in the context of the given `data`,
	allowing to calculate the size of variable-size structures
	
	- data : data that would be packed
	- refdata : list of values that are referenced by external references in
			the structure (e.g. `#1` uses refdata[1] as a count)"""
	stct = Struct(structure)
	return stct.packed_size(*data, refdata=refdata)
