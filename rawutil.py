# -*- coding:utf-8 -*-
# MIT License
#
# Copyright (c) 2017-2022 Tyulis
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
import builtins
import binascii
import collections

__version__ = "2.7.4"

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

def bin(val, align=0):
	if isinstance(val, int):
		return builtins.bin(val).lstrip('0b').zfill(align)
	elif type(val) in (bytes, bytearray, list, tuple):
		return ''.join([builtins.bin(b).lstrip('0b').zfill(8) for b in val]).zfill(align)
	else:
		raise TypeError('Int, bytes or bytearray object is needed')

def hex(val, align=0):
	if isinstance(val, int):
		return builtins.hex(val).lstrip('0x').zfill(align)
	else:
		return binascii.hexlify(bytes(val)).decode('ascii').zfill(align)


def hextoint(hx):
	return int(hx, 16)


def hextobytes(hx):
	if type(hx) == str:
		hx = hx.encode('ascii')
	return binascii.unhexlify(hx)


class FormatError (Exception):
	pass


class OperationError (Exception):
	pass

class DataError (OperationError):
	pass

class ResolutionError (OperationError):
	pass


def _error_context(message, format, position):
	return message + "\n\tIn format '" + format + "', position " + str(position) + "\n\t" + ('-' * (11+position)) + "^"


class _Reference (object):
	__slots__ = ("type", "value")

	Relative = 1
	Absolute = 2
	External = 3

	_REFERENCE_TYPE_NAMES = {0: None, Relative: "relative", Absolute: "absolute", External: "external"}

	def __init__(self, type, value):
		self.type = type
		self.value = value

	def __repr__(self):
		return self.__class__.__name__ + "(" + str(self.type) + ", " + str(self.value) + ")"


class _Token (object):
	__slots__ = ("count", "type", "content", "position")

	def __init__(self, count, type, content, position):
		self.count = count
		self.type = type
		self.content = content
		self.position = position

	def __repr__(self):
		return self.__class__.__name__ + "(" + repr(self.count) + ", '" + self.type + "', " + repr(self.content) + ", " + repr(self.position) + ")"


def _read(data, length=-1):
	readdata = data.read(length)
	if len(readdata) < length:
		raise IndexError("Not enough data to read")
	return readdata

def _list_identity(*elements):
	return list(elements)

_GROUP_CHARACTERS = {"(": ")", "[": "]", "{": "}"}
_NO_MULTIPLE = "{|$"
_END_STRUCTURE = "{$"
_INTEGER_ELEMENTS = {  # (signed, size in bytes)
	"b": (True, 1), "B": (False, 1), "h": (True, 2), "H": (False, 2),
	"u": (True, 3), "U": (False, 3), "i": (True, 4), "I": (False, 4),
	"l": (True, 4), "L": (False, 4), "q": (True, 8), "Q": (False, 8),
}
_FLOAT_ELEMENTS = {  # (size in bytes, exponent bits, factor bits, -exponent, maxvalue)
	"e": (2, 5, 10, 15), "f": (4, 8, 23, 127), "d": (8, 11, 52, 1023), "F": (16, 15, 112, 16383),
}
_STRUCTURE_CHARACTERS = {  # (size in bytes or None if indeterminate, referencable, direct count or None if not counted at all)
	"?": (1, True, True), "b": (1, True, True), "B": (1, True, True),
	"h": (2, True, True), "H": (2, True, True), "u": (3, True, True), "U": (3, True, True),
	"i": (4, True, True), "I": (4, True, True), "l": (4, True, True), "L": (4, True, True),
	"q": (8, True, True), "Q": (8, True, True), "e": (2, False, True), "f": (4, False, True),
	"d": (8, False, True), "F": (16, False, True), "c": (1, False, True), "s": (1, False, False),
	"n": (None, False, True), "X": (1, False, False), "|": (0, False, None), "a": (-1, False, False),
	"x": (1, False, True), "$": (None, False, False),
	"(": (None, False, False), "[": (None, False, False), "{": (None, False, False),
}

class Struct (object):
	"""Object that denotes a binary structure
	A Struct compiles a format once and for all, significantly
	improving performance for reused structures compared to standalone
	functions"""

	__slots__ = ("format", "tokens", "byteorder", "names", "forcebyteorder", "safe_references")

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
		self.safe_references = safe_references
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
			self._parse_struct(format)
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

	def unpack(self, data, names=None, refdata=()):
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
		"""

		if hasattr(data, "read") and hasattr(data, "tell"):  # From file-like object
			unpacked = self._unpack_file(data, self.tokens, refdata)
		else:  # From bytes-like objet
			unpacked = self._unpack_file(io.BytesIO(data), self.tokens, refdata)

		result_converter = self._build_result_converter(names)
		return result_converter(*unpacked)

	def unpack_from(self, data, offset=None, names=None, refdata=(), getptr=False):
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
		"""

		if hasattr(data, "read") and hasattr(data, "tell"):  # From file-like object
			if offset is not None:
				data.seek(offset)
			unpacked = self._unpack_file(data, self.tokens, refdata)
		else:  # From bytes-like objet
			data = io.BytesIO(data)
			if offset is not None:
				data.seek(offset)
			unpacked = self._unpack_file(data, self.tokens, refdata)

		result_converter = self._build_result_converter(names)
		unpacked = result_converter(*unpacked)

		if getptr:
			return unpacked, data.tell()
		else:
			return unpacked

	def pack(self, *data, refdata=()):
		"""Pack data as bytes according to this structure

		- data : all elements to pack, in order
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		"""
		data = list(data)

		if len(data) > 0 and hasattr(data[-1], "write") and hasattr(data, "seek"):  # Into file-like object
			out = data.pop(-1)
			self._pack_file(out, data, refdata)
		else:
			out = io.BytesIO()
			self._pack_file(out, data, refdata)
			out.seek(0)
			return out.read()

	def pack_into(self, buffer, offset, *data, refdata=()):
		"""Pack data into an existing buffer at the given position

		- buffer : writable bytes-like object (e.g. a bytearray), where the data
		        will be written
		- offset : position in the buffer to start writing from
		- data : all elements to pack, in order
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		"""
		out = io.BytesIO()
		self._pack_file(out, data, refdata)
		out.seek(0)
		packed = out.read()
		buffer[offset: offset + len(packed)] = packed

	def pack_file(self, file, *data, position=None, refdata=()):
		"""Pack data into a file-like object

		- file : writable binary file-like object, where the data will be
		        written. It is left after the data that has been written
		- data : all elements to pack, in order
		- position : absolute position in the file to start writing from.
		        Defaults to the current position
		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		"""
		if position is not None:
			file.seek(position)
		self._pack_file(file, data, refdata)

	def iter_unpack(self, data, names=None, refdata=()):
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
		"""

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
			unpacked = self._unpack_file(buffer, self.tokens, refdata)
			yield result_converter(*unpacked)

	def calcsize(self, refdata=None, tokens=None):
		"""Calculate the size in bytes of the data represented by this structure

		- refdata : list of values that are referenced by external references in
		        the structure (e.g. `#1` uses refdata[1] as a count)
		When the size is indeterminate (elements that require actual data as
		context, like null-terminated strings, internal references, …), fail
		with a FormatError
		"""
		if tokens is None:
			tokens = self.tokens
		size = 0
		alignref = 0
		for token in tokens:
			if isinstance(token.count, _Reference):
				if token.count.type == 3 and refdata is not None:
					count = refdata[token.count.value]
				else:
					raise FormatError(_error_context("Impossible to compute the size of a structure with references", self.format, token.position))
			else:
				count = token.count

			if token.type in "[(":
				size += count * self.calcsize(refdata, token.content)
			elif token.type == "{":
				raise FormatError(_error_context("Impossible to compute the size of a structure with {} iterators", self.format, token.position))
			elif token.type == "|":
				alignref = size
			else:
				elementsize, referencable, directcount = _STRUCTURE_CHARACTERS[token.type]
				if elementsize is None:
					raise FormatError(_error_context("Impossible to compute the size of a structure with '" + token.type + "' elements", self.format, token.position))
				elif elementsize == -1:
					refdistance = size - alignref
					padding = count - (refdistance % count or count)
					size += padding
				else:
					size += count * elementsize
		return size

	def _parse_struct(self, format):
		format = format.strip()
		if format[0] in tuple(ENDIANNAMES.keys()):
			self.byteorder = ENDIANNAMES[format[0]]
			self.forcebyteorder = True
			format = format[1:]
			startpos = 1
		else:
			startpos = 0

		self.tokens = self._parse_substructure(format, startpos)

	def _parse_substructure(self, format, startpos):
		tokens = []
		cut_countable = False
		first_countable = 0
		last_countable = 0
		ptr = 0
		while ptr < len(format):
			if format[ptr].isspace():
				ptr += 1
				continue
			elif format[ptr] in ["'", '"']:
				ptr += 1
				while format[ptr] not in ["'", '"']:
					ptr += 1
				ptr += 1
				continue

			startptr = ptr
			# References
			if format[ptr] == "/":
				ptr += 1
				if format[ptr] == "p":  # Relative
					reftype = _Reference.Relative
					ptr += 1
				else:  # Absolute
					reftype = _Reference.Absolute
			elif format[ptr] == "#":  # External reference
				reftype = _Reference.External
				ptr += 1
			else:  # Normal count
				reftype = None

			# Parsing count
			countstr = ""
			while format[ptr].isdigit():
				countstr += format[ptr]
				ptr += 1

			if len(countstr) == 0:
				if reftype is not None:
					raise FormatError(_error_context("No reference index", self.format, startptr + startpos))
				count = 1
			else:
				count = int(countstr)
				if reftype is not None:
					if reftype == _Reference.Absolute:
						if not cut_countable and count >= first_countable:
							raise FormatError(_error_context("Invalid reference index : absolute reference unambiguously references itself or elements located after itself", self.format, startptr + startpos))
						elif self.safe_references and count >= first_countable:
							raise FormatError(_error_context("Unsafe reference index : absolute reference references in or after an indeterminate amount of elements (typically a reference). If it is intended, use the parameter safe_references=False of the Struct() constructor", self.format, startptr + startpos))
					if reftype == _Reference.Relative:
						if count <= 0:
							raise FormatError(_error_context("Invalid reference index : relative reference references itself (the immediate previous element is /p1)", self.format, startptr + startpos))
						elif not cut_countable and count > last_countable:
							raise FormatError(_error_context("Invalid reference index : relative reference references beyond the beginning of the format", self.format, startptr + startpos))
						elif self.safe_references and count > last_countable:
							raise FormatError(_error_context("Unsafe reference index : relative reference references in or beyond an indeterminate amount of elements (typically a reference). If it is intended, use the parameter safe_references=False of the Struct() constructor", self.format, startptr + startpos))
					count = _Reference(reftype, count)

			if format[ptr] not in _STRUCTURE_CHARACTERS:
				raise FormatError(_error_context("Unrecognised format character '" + format[ptr] + "'", self.format, startptr + startpos))
			size, referencable, directcount = _STRUCTURE_CHARACTERS[format[ptr]]
			# Groups
			if format[ptr] in _GROUP_CHARACTERS:
				openchar = format[ptr]
				closechar = _GROUP_CHARACTERS[format[ptr]]
				subformat = ""
				ptr += 1
				elements = 1
				level = 1
				while level > 0 and ptr < len(format):
					subformat += format[ptr]
					if format[ptr] == openchar:
						level += 1
					elif format[ptr] == closechar:
						level -= 1
					ptr += 1
				if level > 1:
					raise FormatError(_error_context("Group starting with '" + openchar + "' is never closed", self.format, startptr + startpos))
				subformat = subformat[:-1]
				type = openchar
				content = self._parse_substructure(subformat, startptr + startpos)
			else:  # Standard structure elements
				type = format[ptr]
				content = None
				ptr += 1

				# Get the number of actual elements in this token, or None if indeterminate (reference)
				if directcount is None:
					elements = 0
				elif directcount:
					elements = None if isinstance(count, _Reference) else count
				else:
					elements = 1
			if count != 1 and type in _NO_MULTIPLE:
				raise FormatError(_error_context("'" + type + "' elements should not be multiple", self.format, startptr + startpos))
			if ptr < len(format) and type in _END_STRUCTURE:
				raise FormatError(_error_context("'" + type + "' terminates the structure, there should be nothing else afterwards", self.format, startptr + startpos))

			# Slight optimization for pack and unpack : reduce things like IIII -> 4I
			if directcount and len(tokens) > 0 and type == tokens[-1].type and not isinstance(count, _Reference) and not isinstance(tokens[-1].count, _Reference):
				tokens[-1].count += count
			else:
				token = _Token(count, type, content, startptr)
				tokens.append(token)

			if elements is None:  # Uncountable interruption
				cut_countable = True
				last_countable = 0
			else:  # Add to the other countable elements
				last_countable += elements
				if not cut_countable:
					first_countable += elements

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
				if token.count.type == 1:    # Relative
					value = unpacked[-token.count.value]
				elif token.count.type == 2:  # Absolute
					value = unpacked[token.count.value]
				elif token.count.type == 3:  # External
					value = refdata[token.count.value]
				return value.__index__()
			except AttributeError as exc:
				raise TypeError(_error_context("Count from " + _Reference._REFERENCE_TYPE_NAMES[token.count.type] + " reference index " + str(token.count.value) + " must be an integer", self.format, token.position)) from exc
			except IndexError as exc:
				raise ResolutionError(_error_context("Invalid " + _Reference._REFERENCE_TYPE_NAMES[token.count.type] + " reference index : " + str(token.count.value), self.format, token.position)) from exc
		else:
			return token.count

	def _decode_float(self, data, exponentsize, mantissasize):
		maxed_exponent = (1 << exponentsize) - 1

		encoded = int.from_bytes(data, byteorder=self.byteorder, signed=False)
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
			min_biased_exponent = 2 - (1 << (exponentsize - 1))
			max_biased_exponent = (1 << (exponentsize - 1)) - 1
			biased_exponent = max(min_biased_exponent, min(math.floor(math.log2(value)), max_biased_exponent))
			normalized = value / 2**biased_exponent

			if normalized >= 2:
				raise OverflowError(_error_context("Floating-point value " + str(value) + " is too big for " + str(size*8) + " bits float", self.format, token.position))
			elif normalized < 1:  # Still too small -> subnormal
				exponent = 0
			else:  # Normal number, strip the trivial 1
				normalized -= 1
				exponent = biased_exponent + max_biased_exponent

			mantissa = normalized * (1 << mantissasize)
			rounded_mantissa = int(mantissa)
			remainder = mantissa - rounded_mantissa
			# Staying with struct, round to the nearest, ties to even
			if 0.5 < remainder < 1 or (remainder == 0.5 and rounded_mantissa & 1):
				rounded_mantissa += 1
				# On the upper edge of the value range, it is possible that the
				# rounding made the value overflow without being detected earlier
				if rounded_mantissa >= (1 << mantissasize):
					raise OverflowError(_error_context("Floating-point value " + str(value) + " is too big for " + str(size*8) + " bits float", self.format, token.position))
			mantissa = rounded_mantissa
		return sign, exponent, mantissa


	def _unpack_file(self, data, tokens, refdata):
		alignref = data.tell()
		unpacked = []

		for token in tokens:
			count = self._resolve_count(token, unpacked, refdata)

			try:
				# Groups
				if token.type == "(":
					multigroup = []
					for i in range(count):
						subgroup = self._unpack_file(data, token.content, refdata)
						multigroup.extend(subgroup)
					unpacked.append(multigroup)
				elif token.type == "[":
					sublist = []
					for i in range(count):
						subgroup = self._unpack_file(data, token.content, refdata)
						sublist.append(subgroup)
					unpacked.append(sublist)
				elif token.type == "{":
					sublist = []
					while True:
						try:
							subgroup = self._unpack_file(data, token.content, refdata)
						except DataError:
							break
						sublist.append(subgroup)
					unpacked.append(sublist)
				# Control
				elif token.type == "|":
					alignref = data.tell()
				elif token.type == "a":
					refdistance = data.tell() - alignref
					padding = count - (refdistance % count or count)
					data.seek(padding, 1)
				elif token.type == "$":
					unpacked.append(_read(data))
				# Elements
				elif token.type in _INTEGER_ELEMENTS:
					signed, size = _INTEGER_ELEMENTS[token.type]
					groupdata = _read(data, size * count)
					for i in range(count):
						unpacked.append(int.from_bytes(groupdata[i*size: (i+1)*size], byteorder=self.byteorder, signed=signed))
				elif token.type in _FLOAT_ELEMENTS:
					size, exponentsize, mantissasize, bias = _FLOAT_ELEMENTS[token.type]
					groupdata = _read(data, size * count)
					for i in range(count):
						elementdata = groupdata[i*size: (i+1)*size]
						decoded = self._decode_float(elementdata, exponentsize, mantissasize)
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
				raise DataError(_error_context("No data remaining to read element '" + token.type + "'", self.format, token.position))

		return unpacked

	def _pack_file(self, out, data, refdata, tokens=None):
		if tokens is None:
			tokens = self.tokens
		position = 0
		alignref = out.tell()
		for token in tokens:
			count = self._resolve_count(token, data[:position], refdata)
			try:
				# Groups
				if token.type == "(":
					grouppos = 0
					for _ in range(count):
						grouppos += self._pack_file(out, data[position][grouppos:], refdata, token.content)
					position += 1
				elif token.type == "[":
					for _, group in zip(range(count), data[position]):
						self._pack_file(out, group, refdata, token.content)
					position += 1
				elif token.type == "{":
					for group in data[position]:
						self._pack_file(out, group, refdata, token.content)
					position += 1
				# Control
				elif token.type == "|":
					alignref = out.tell()
				elif token.type == "a":
					refdistance = out.tell() - alignref
					padding = count - (refdistance % count or count)
					out.write(b"\x00" * padding)
				elif token.type == "$":
					out.write(data[position])
					position += 1
				elif token.type in _INTEGER_ELEMENTS:
					signed, size = _INTEGER_ELEMENTS[token.type]
					elementdata = b""
					try:
						for _ in range(count):
							elementdata += data[position].to_bytes(size, byteorder=self.byteorder, signed=signed)
							position += 1
					except AttributeError as exc:
						raise TypeError(_error_context("Wrong type for format '" + token.type + "', the given object must be an integer or have a .to_bytes() method similar to int", self.format, token.position))
					out.write(elementdata)
				elif token.type in _FLOAT_ELEMENTS:
					size, exponentsize, mantissasize, bias = _FLOAT_ELEMENTS[token.type]
					elementdata = b""
					for _ in range(count):
						decoded = data[position]
						position += 1

						sign, exponent, mantissa = self._build_float(token, decoded, exponentsize, mantissasize)
						encoded = (((sign << exponentsize) | exponent) << mantissasize) | mantissa
						elementdata += encoded.to_bytes(size, byteorder=self.byteorder, signed=False)
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
						raise OperationError(_error_context("Length of structure element 's' (" + str(count) + " and data '" + repr(data[position]) + "' do not match", self.format, token.position))
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
				raise DataError(_error_context("No data remaining to pack into element '" + token.type + "'", self.format, token.position))
		return position

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
			if count.type == 1:  # relative
				return "/p" + str(count.value)
			elif count.type == 2:  # absolute
				return "/" + str(count.value)
			elif count.type == 3:  # external
				return "#" + str(count.value)
		else:
			return str(count)

	def _tokens_to_format(self, tokens):
		format = ""
		for token in tokens:
			if token.type in _GROUP_CHARACTERS:
				subformat = self._tokens_to_format(token.content)
				format += self._count_to_format(token.count) + token.type + subformat + _GROUP_CHARACTERS[token.type] + " "
			else:
				format += self._count_to_format(token.count) + token.type + " "
		return format.strip()

	def _max_external_reference(self, tokens):
		maxref = -1
		for token in tokens:
			if isinstance(token.count, _Reference):
				if token.count.type == 3:
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
				if token.count.type == 3:
					token.count.value += leftexternals
			if token.content is not None:
				self._fix_external_references(token.content, leftexternals)

	def _add_structs(self, lefttokens, righttokens):
		leftexternals = self._max_external_reference(lefttokens) + 1
		right_has_references = any(isinstance(token.count, _Reference) and token.count.type == _Reference.Absolute for token in righttokens)

		outtokens = []
		leftsize = 0
		for token in lefttokens:
			if token.type in ("{", "$"):
				raise FormatError("'" + token.type + ("}" if token.type == "{" else "") + "' forces the end of the structure, you can’t add or multiply structures if it causes those elements to be in the middle of the resulting structure")
			elif right_has_references and isinstance(token.count, _Reference) and _STRUCTURE_CHARACTERS[token.type][2]:
				raise FormatError("The left operand has an indeterminate amount of elements, impossible to fix right side absolute references")
			outtokens.append(copy.deepcopy(token))

			if leftsize is not None:
				directcount = _STRUCTURE_CHARACTERS[token.type][2]
				if directcount is None:
					pass
				elif directcount:
					if isinstance(token.count, _Reference):
						leftsize = None
					else:
						leftsize += token.count
				else:
					leftsize += 1

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
			directcount = _STRUCTURE_CHARACTERS[token.type][2]
			if blocksize is not None:
				if directcount is None:
					pass
				elif directcount:
					if isinstance(token.count, _Reference):
						blocksize = None
					else:
						blocksize += token.count
				else:
					blocksize += 1
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
					if newtoken.count.type == 2:  # absolute
						newtoken.count.value += size
					elif newtoken.count.type == 3:  # external
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


class TypeUser (object):
	def __init__(self, byteorder="@"):
		self.byteorder = ENDIANNAMES[byteorder]

	def unpack(self, structure, data, names=None, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.unpack(data, names, refdata)

	def unpack(self, structure, data, names=None, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.unpack(data, names, refdata)

	def unpack_from(self, structure, data, offset=None, names=None, refdata=(), getptr=False):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.unpack_from(data, offset, names, refdata, getptr)

	def iter_unpack(self, structure, data, names=None, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.iter_unpack(data, names, refdata)

	def pack(self, structure, *data, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.pack(*data, refdata=refdata)

	def pack_into(self, structure, buffer, offset, *data, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.pack_into(buffer, offset, *data, refdata=refdata)

	def pack_file(self, structure, file, *data, position=None, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.pack_file(file, *data, position=position, refdata=refdata)

	def calcsize(self, structure, refdata=()):
		stct = Struct(structure)
		if not stct.forcebyteorder:
			stct.setbyteorder(self.byteorder)
		return stct.calcsize()

def _readermethod(stct):
		def _TypeReader_method(self, data, ptr=None):
			(result, ), ptr = self.unpack_from(stct, data, ptr, getptr=True)
			return result, ptr
		return _TypeReader_method

class TypeReader (TypeUser):
	bool = _readermethod(Struct("?"))
	int8 = _readermethod(Struct("b"))
	uint8 = _readermethod(Struct("B"))
	int16 = _readermethod(Struct("h"))
	uint16 = _readermethod(Struct("H"))
	int24 = _readermethod(Struct("u"))
	uint24 = _readermethod(Struct("U"))
	int32 = _readermethod(Struct("i"))
	uint32 = _readermethod(Struct("I"))
	int64 = _readermethod(Struct("q"))
	uint64 = _readermethod(Struct("Q"))
	half = float16 = _readermethod(Struct("e"))
	single = float = float32 = _readermethod(Struct("f"))
	double = float64 = _readermethod(Struct("d"))
	quad = float128 = _readermethod(Struct("F"))
	string = _readermethod(Struct("n"))

	def tobits(self, n, align=8):
		return [int(bit) for bit in bin(n, align)]

	def bit(self, n, bit, length=1):
		mask = ((2 ** length) - 1) << bit
		return (n & mask) >> (bit - length)

	def nibbles(self, n):
		return (n >> 4, n & 0xf)

	def signed_nibbles(self, n):
		high = (n >> 4)
		if high >= 8:
			high -= 16
		low = (n & 0xf)
		if low >= 8:
			low -= 16
		return high, low

	def utf16string(self, data, ptr):
		subdata = data[ptr:]
		s = []
		zeroes = 0
		for i, c in enumerate(subdata):
			if c == 0:
				zeroes += 1
			else:
				zeroes = 0
			s.append(c)
			if zeroes >= 2 and i % 2 == 1:
				break
		endian = 'le' if self.byteorder == 'little' else 'be'
		return bytes(s[:-2]).decode('utf-16-%s' % endian), ptr + i

def _writermethod(stct):
		def _TypeWriter_method(self, data, out=None):
			if out is None:
				return self.pack(stct, data)
			else:
				self.pack(stct, data, out)
		return _TypeWriter_method

class TypeWriter (TypeUser):
	bool = _writermethod(Struct("?"))
	int8 = _writermethod(Struct("b"))
	uint8 = _writermethod(Struct("B"))
	int16 = _writermethod(Struct("h"))
	uint16 = _writermethod(Struct("H"))
	int24 = _writermethod(Struct("u"))
	uint24 = _writermethod(Struct("U"))
	int32 = _writermethod(Struct("i"))
	uint32 = _writermethod(Struct("I"))
	int64 = _writermethod(Struct("q"))
	uint64 = _writermethod(Struct("Q"))
	half = float16 = _writermethod(Struct("e"))
	single = float = float32 = _writermethod(Struct("f"))
	double = float64 = _writermethod(Struct("d"))
	quad = float128 = _writermethod(Struct("F"))

	def nibbles(self, high, low):
		return (high << 4) + (low & 0xf)

	def signed_nibbles(self, high, low):
		if high < 0:
			high += 16
		if low < 0:
			low += 16
		return (high << 4) + (low & 0xf)

	def string(self, data, align=0, out=None):
		if isinstance(data, str):
			s = data.encode('utf-8')
		if align < len(s) + 1:
			align = len(s) + 1
		res = struct.pack('%s%ds' % (self.byteorder, align), s)
		if out is None:
			return res
		else:
			out.write(res)

	def utf16string(self, data, align=0, out=None):
		endian = 'le' if self.byteorder == 'little' else 'be'
		s = data.encode('utf-16-%s' % endian) + b'\x00\x00'
		if align < len(s) + 2:
			align = len(s) + 2
		res = struct.pack('%s%ds' % (self.byteorder, align), s)
		if out is None:
			return res
		else:
			out.write(res)

	def pad(self, num):
		return b'\x00' * num

	def align(self, data, alignment):
		if isinstance(data, int):
			length = data
		else:
			length = len(data)
		padding = alignment - (length % alignment or alignment)
		return b'\x00' * padding


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
