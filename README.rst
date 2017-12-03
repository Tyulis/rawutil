rawutil
=======
A single-file pure-python module to deal with binary packed data

Rawutil documentation
=====================

**rawutil** is a python3 module to read and write binary packed data

There is two ways to use it:

-	Like *struct*, with string structures
-	With the TypeReader and TypeWriter objects

1-String structures
-------------------
rawutil can be used like struct, with structures stored as strings. rawutil is almost fully compatible with struct. If in a program, you can replace all instances of "struct" by "rawutil", it should work exactly same (see below for problems).

rawutil has the same 3 main functions as struct:

	pack(stct, *data) -> bytes
		Packs the elements in a bytes object as described by the stucture specified by the stct argument

	pack(stct, *data, file) -> None
		Packs the elements in the given file-like object as described by the stucture specified by the stct argument

	unpack(stct, data, refdata=())
		Unpacks the binary data given as a bytes object as described by the structure in the stct argument, and returns elements as a list
		data can also be a file-like object. In this case, unpacking will start at the beginning of the file (it performs a file.seek(0))
		The refdata option is a tuple which contains the data used by the external references, see below.
		Note that unlike its struct equivalent, it won't raise an exception if the data length doesn't match the structure length.

	unpack_from(stct, data, offset=0, refdata=(), getptr=False)
		Unpacks the data as described by the stct argument from the specified offset, and returns elements as a list
		data can also be a file-like object. In this case, unpacking will start at the specified location (performs file.seek(offset))
		The refdata argument is used for external references, see below
		If getptr is True, this function returns *unpacked, ptr* instead of only *unpacked*. The pointer is the offset where the unpacking has ended


rawutil structures can match variable lengths, so there is not any *calcsize* function.

String structures reference
----------------------------
The structure is a str object.

It can begin by a character to specify the byte order, exactly like *struct*:

+----+----------------------------------------------+
|Chr.| Effect                                       |
+====+==============================================+
| =  |  Uses the system byte order and alignment    |
+----+----------------------------------------------+
| @  |  Uses the system byte order without alignment|
+----+----------------------------------------------+
| !  |  Network byte order (same as >)              |
+----+----------------------------------------------+
| >  |  Big endian                                  |
+----+----------------------------------------------+
| <  |  Little endian                               |
+----+----------------------------------------------+

When there is no byte order mark, the byte order defaults to @

Then, the format string really begins. Note that, unlike *struct*'s ones, rawutil stuctures can contain as many spaces as you want.

Elements
--------
First, all elements usable in *struct* can be used with rawutil:

+-----+--------+--------------------------------------------------------+
|Chr. | Type   | Description                                            |
+=====+========+========================================================+
|  c  | char   | Returns a 1-byte bytes object                          |
+-----+--------+--------------------------------------------------------+
|  b  | int8   | Signed 8-bits (1 byte) integer                         |
+-----+--------+--------------------------------------------------------+
|  B  | uint8  | Unsigned 8-bits integer                                |
+-----+--------+--------------------------------------------------------+
|  ?  | bool   | Returns a boolean from a byte (False if 0, else True)  |
+-----+--------+--------------------------------------------------------+
|  h  | int16  | Signed 16-bits (2 bytes) integer                       |
+-----+--------+--------------------------------------------------------+
|  H  | uint16 | Unsigned 16-bits integer                               |
+-----+--------+--------------------------------------------------------+
|  i  | int32  | Signed 32-bits (4 bytes) integer                       |
+-----+--------+--------------------------------------------------------+
|  I  | uint32 | Unsigned 32-bits integer                               |
+-----+--------+--------------------------------------------------------+
|  l  | int32  | Signed 32-bits (4 bytes) integer                       |
+-----+--------+--------------------------------------------------------+
|  L  | uint32 | Unsigned 32-bits integer                               |
+-----+--------+--------------------------------------------------------+
|  q  | int64  | Signed 64-bits (8 bytes) integer                       |
+-----+--------+--------------------------------------------------------+
|  Q  | uint64 | Unsigned 64-bits integer                               |
+-----+--------+--------------------------------------------------------+
|  f  | float  | 32-bits float                                          |
+-----+--------+--------------------------------------------------------+
|  d  | double | 64-bits double                                         |
+-----+--------+--------------------------------------------------------+
|  s  | string | Returns a bytes object                                 |
+-----+--------+--------------------------------------------------------+
|  x  | void   | Padding byte: doesn't return anything                  |
+-----+--------+--------------------------------------------------------+

Note that s should be used with a length: "12s" will return a 12-bytes bytes object, unlike "12c" which returns 12 1-bytes bytes objects. Note also that the P and N are not available, and n is not used as an ssize_t like in *struct*

There is also new format characters introduced in rawutil:

+-----+--------+-------------------------------------------------------------+
|Chr. | Type   | Description                                                 |
+=====+========+=============================================================+
|  u  | int24  | Signed 24-bits (3 bytes) integer                            |
+-----+--------+-------------------------------------------------------------+
|  U  | uint24 | Unsigned 24-bits integer                                    |
+-----+--------+-------------------------------------------------------------+
|  n  | string | Null-terminated string                                      |
+-----+--------+-------------------------------------------------------------+
|  a  | pad    | Alignment: aligns to a multiple of the specified number     |
+-----+--------+-------------------------------------------------------------+
|  X  | hex    | Works like s but returns the bytes as an hexadecimal string |
+-----+--------+-------------------------------------------------------------+
|  $  | bytes  | Go to the end                                               |
+-----+--------+-------------------------------------------------------------+

The "n" element returns a bytes object. The string is read from the current pointer position, until a null byte (0x00) is found. The null byte is not included in the returned string. At packing, it packs a bytes object, and adds a null byte at the end

The "a" element performs an aligment. It should be used like "20a": the number represents the alignment. At unpacking, it places the pointer at the next multiple of the alignment. It doesn't return anything. At packing, it will add null bytes until a multiple of the aligment length is reached (skip it in the data arguments)

The "$" element represents the end. At unpacking, it returns all the remaining unread data as a bytes object, and ends the reading (it places the pointer at the data's end). At packing, it appends the corresponding bytes object in the data arguments at the end of the packed bytes, and ends the packing.

Then, rawutil adds groups and iterators.
----------------------------------------

These elements can group other elements and unpack them several times

The () element represents a group. It should be used like that:

	"4s I2H (2B 2H) 20a"

All elements between the brackets will be unpacked as a substructure, in a list. Here, it can returns for example:

	[b'test', 10000, 326, 1919, [11, 19, 112, 1222] , b'\x00\x00']

At packing, all data packed in the group should be in a list, like this.

Then, the [] element is an iterator. It should be used like that:

	"h 4[2B]"

It will read the substructure as many times as precised before the [. It will returns a list of lists, like this:

	[-1234, [[11, 12], [111, 112], [9, 99], [31, 112]]]

Finally, the {} iterator will iterate until the end of data is reached (so don't precise the iterations count). Like [], it returns a list of lists. For examples, this structure:

	'4s {Bn}'

With this data:

	b'TEST\x01Yes\x00\x02No\x00'

Returns:

	[b'TEST', [[1, b'Yes'], [2, b'No']]]


Finally, rawutil includes references
------------------------------------

There is two different types of references: external and internal references.

The external references are represented with '#'. They are replaced by the corresponding element in the refdata argument. For example, with this call::

	data = b'<some bytes>!'
	rawutil.unpack('#0c #1s #2c', data, refdata=(1, len(data) - 3, 2))

"#0" is replaced by 1, "#1" by (len(data) - 3), here 10, and "#2" by 2: the final structure is '1c 10s 2c' so it will return:

	[b'<', b'some bytes', b'>', b'!']

Then, the internal references. They are represented by a "/", and should be used like this:

	'4s 2B /2[2s]'

The number near the "/" is the index of the reference. The reference will be replaced by the unpacked element at the specified index, here the second "B", so with this data:

	b'TEST\xff\x06zyXWvuTSrqPO'

It will return:

	[b'TEST', 255, 6, [[b'zy'], [b'XW'], [b'vu'], [b'TS'], [b'rq'], [b'PO']]]

Here, the element 2 of the unpacked elements contains 6, so the "/2" is replaced by "6", so it is interpreted as '4s 2B 6[2s]', so [2s] is unpacked as many times as specified by the element 2.

Internal references can also be relative, with '/p'. You can use for example this structure:

	'2B /p2[2s]'

With this data:

	b'\x04\xffJJkkLLmm'

It will return:

	[4, 255, [[b'JJ', b'kk', b'LL', b'mm']]]

So the "/p2" will be replaced by the element situated 2 elements before, here, the first B, so here, 4

Objects
=======

You can also use rawutil with objects TypeReader and TypeWriter.

	TypeReader(byteorder='@')
	TypeWriter(byteorder='@')

The byteorder argument is the used byteorder mark, exactly like the format strings' one. You can also specify it using the byteorder attribute of these objects.

You can easily subclass it to create a reader or writer class for the format you want.

These two objects have the pack, unpack and unpack_from methods, which are exactly the sames as the module-level ones, but if the byte order is not precised in the structure, it defaults to the byteorder attribute instead of "@".

First, the TypeReader object can read elements from a bytes-like or file-like object. It has the following methods:

	bit(n, bit, length=1)
		Returns the specified bits in the n integer. Returns (length) bits
	nibbles(n)
		Returns the high and low nibbles of a byte
	signed_nibbles(n)
		Returns the high and low signed nibbles of a byte

All its other methods takes 2 arguments:

	TypeReader.uint8(data, ptr=0)

ptr is the offset to start reading. If None, reading starts at the current file position (given by file.tell()), or at 0 if data is a bytes-like object. All its other methods returns (unpacked, ptr), where unpacked is the unpacked elements, and ptr is the offset where the reading ended.

The TypeReader objects have the following methods::

	uint8(data, ptr=None)
	uint16(data, ptr=None)
	uint24(data, ptr=None)
	uint32(data, ptr=None)
	uint64(data, ptr=None)
	int8(data, ptr=None)
	int16(data, ptr=None)
	int24(data, ptr=None)
	int32(data, ptr=None)
	int64(data, ptr=None)
	float32(data, ptr=None) = float(...)
	double(data, ptr=None)  #64 bits double
	string(data, ptr=None)  #null-terminated string, like the "n" format character
	utf16string(data, ptr=None)  #null-terminated UTF-16 string

Then, the TypeWriter object can pack some elements. It has the following methods: (data argument is the element to pack, out can be the output file-like objects)::

	nibbles(high, low)  #returns the byte formed by the two nibbles
	signed_nibbles(high, low)  #idem with signed nibbles
	int8(data, out=None)
	int16(data, out=None)
	int24(data, out=None)
	int32(data, out=None)
	int64(data, out=None)
	uint8(data, out=None)
	uint16(data, out=None)
	uint24(data, out=None)
	uint32(data, out=None)
	uint64(data, out=None)
	float32(data, out=None) = float(...)
	double(data, out=None)  #64 bits double
	string(data, align=0, out=None)  #align is the minimal size to pack. Packs a bytes object as a null-terminated string
	utf16string(data, align=0, out=None)
	pad(num)  #Returns the given number of null bytes
	align(data, alignnment)  #Returns null bytes to fill to a multiple of the alignment

There are not any non-builtin dependencies.
