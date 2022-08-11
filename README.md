# Rawutil

*A pure-python and lightweight module to read and write binary data*

## Introduction

Rawutil is a module aimed at reading and writing binary data in python in the same way as the built-in `struct` module, but with more features.
The rawutil's interface is thus compatible with `struct`, with a few small exceptions, and many things added.
It does not have any non-builtin dependency.

### What is already in struct

- Unpack and pack fixed structures from/to bytes (`pack`, `pack_into`, `unpack`, `unpack_from`, `iter_unpack`, `calcsize`)
- `Struct` objects that allow to parse one and for all a structure that may be used several times

### What is different compared to struct

- Some rarely-used format characters are not in rawutil (`N`, `P` and `p` are not available, `n` is used for a different purpose)
- There is no consideration for native size and alignment, thus the `@` characters simply applies system byte order with standard sizes and no alignment, just like `=`
- There are several differences in error handling that are described below

### What has been added to struct

- Reading and writing files and file-like objects
- New format characters, to handle padding, alignment, strings, ...
- Internal references in structures
- Loops in structures
- New features to handle variable byte order

## Usage

Rawutil exports more or less the same interface as `struct`. In all those functions, `structure` may be a simple format string or a `Struct` object.

### unpack

```python
unpack(structure, data, names=None, refdata=())
```
Unpacks the given `data` according to the `structure`, and returns the unpacked values as a list.

- `structure` is the structure of the data to unpack, as a format string or a `Struct` object
- `data` may be a bytes-like or a file-like object. If it is a file-like object, the data will be unpacked starting from the current position in the file, and will leave the cursor at the end of the data that has been read (effectively reading the data to unpack from the file).
- `names` may be a list of field names for a `namedtuple`, or a callable that takes all unpacked elements in order as arguments, like a `namedtuple` or a `dataclass`.
- `refdata` may be used to easily input external data into the structure, as `#n` references. This will be described in the References part below

Unlike `struct`, this function does not raises any error if the data is larger than the structure expected size.

Examples :

```python
>>> unpack("4B 3s 3s", b"\x01\x02\x03\x04foobar")
(1, 2, 3, 4, b"foo", b"bar")
>>> unpack("<4s #0I", b"ABCD\x10\x00\x00\x00\x20\x00\x00\x00", names=("string", "num1", "num2"), refdata=(2, ))
RawutilNameSpace(string=b'ABCD', num1=16, num2=32)
```

### unpack_from

```python
unpack_from(structure, data, offset=None, names=None, refdata=(), getptr=False)
```

Unpacks the given `data` according to the `structure` starting from the given `position`, and returns the unpacked values as a list

This function works exactly like `unpack`, with two more optional arguments :

- `offset` can be used to specify a starting position to read. In a file-like object, the cursor is moved to the given absolute `offset`, then the data to unpack is read and the cursor is left at the end of the data that has been read. If this parameter is not set, it works like `unpack` and reads from the current position
- `getptr` can be set to True to return the final position in the data, after the unpacked data. The function will then return `(values, end_position)`. If left to False, it works like `unpack` and only returns the values.

Examples :

```python
>>> unpack_from("<4s #0I", b"ABCD\x10\x00\x00\x00\x20\x00\x00\x00", names=("string", "num1", "num2"), refdata=(2, ))
RawutilNameSpace(string=b'ABCD', num1=16, num2=32)
>>> values, endpos = unpack_from("<2I", b"ABCD\x10\x00\x00\x00\x20\x00\x00\x00EFGH", offset=4, getptr=True)
>>> values
[16, 32]
>>> endpos
12
```

### iter_unpack

```python
iter_unpack(structure, data, names=None, refdata=())
```

Returns an iterator that will unpack according to the structure and return the values as a list at each iteration.
The data must be of a multiple of the structure’s length. If `names` is defined, each iteration will return a namedtuple, most like `unpack` and `unpack_from`. `refdata` also works the same.

This function is present mostly to ensure compatibility with `struct`. It is rather recommended to use iterators in structures, that are faster and offer much more control.

Examples :
```python
>>> for a, b, c in iter_unpack("3c", b"abcdefghijkl"):
...     print(a.decode("ascii"), b.decode("ascii"), c.decode("ascii"))
...
a b c
d e f
g h i
j k l
```

### pack

```python
pack(self, *data, refdata=())
```

Packs the given `data` in the binary format defined by `structure`, and returns the packed data as a `bytes` object.
`refdata` is still there to insert external data in the structure using the `#n` references, and is a named argument only.

Note that if the last element of `data` is a writable file-like object, the data will be written into it instead of being returned. This behaviour is deprecated and kept only for backwards-compatibility, to pack into a file you should rather use `pack_file`.

Examples :
```python
>>> pack("<2In", 10, 100, b"String")
b'\n\x00\x00\x00\n\x00\x00\x00String\x00'
>>> pack(">#0B #1I", 10, 100, 1000, 10000, 100000, refdata=(2, 3))
b"\nd\x00\x00\x03\xe8\x00\x00'\x10\x00\x01\x86\xa0"
>>> unpack(">2B3I", _)
[10, 100, 1000, 10000, 100000]
```

### pack_into

```python
pack_into(structure, buffer, offset, *data, refdata=())
```

Packs the given `data` into the given `buffer` at the given `offset` according to the given `structure`. Refdata still has the same usage as everywhere else.

- `buffer` must be a mutable bytes-like object (typically a `bytearray`). The data will be written directly into it at the given position
- `offset` specifies the position to write the data to. It is a required argument.

Examples :

```python
>>> b = bytearray(b"AB----GH")
>>> pack_into("4s", b, 2, b"CDEF")
>>> b
bytearray(b'ABCDEFGH')
```

### pack_file

```python
pack_file(structure, file, *data, position=None, refdata=())
```

Packs the given `data` into the given `file` according to the given `structure`. `refdata` is still there for the external references data.

- `file` can be any binary writable file-like object.
- `position` can be set to pack the data at a specific position in the file. If it is left to `None`, the data will be packed at the current position in the file. In either case, the cursor will end up at the end of the packed data.

Examples :

```python
>>> file = io.BytesIO(b"\x00\x00\x00\x00\x00\x00\x00\x00")
>>> rawutil.pack_file("2B", file, 60, 61)  # Writes at the current position (0)
>>> rawutil.pack_file("c", file, b"A")     # Writes at the current position (now 2)
>>> rawutil.pack_file("2c", file, b"y", b"z", position=6)  # Writes at the given position (6)
>>> file.seek(0)
>>> file.read()
b'<=A\x00\x00\x00yz'
```

### calcsize

```python
calcsize(structure, refdata=())
```

Returns the size of the data represented by the given `structure`.

This function is kept to ensure compatibility with `struct`.
However, rawutil structure are not always of a fixed length, as they use internal references and variable length formats.
Hence `calcsize` only works on fixed-length structures, thus structures that only use :

- Fixed-length format characters (basic types with set repeat count)
- External references (`#0` type references, if you provide their value in `refdata`)
- Iterators with fixed number of repeats (`2(…)` or `5[…]` will work)
- Alignments (structures with `a` and `|`). As long as everything else is fixed, alignments are too.

Trying to compute the size of a structure that includes any of those elements will raise an `FormatError` (basically, anything that depends on the data to read / write) :

- Variable-length format characters (namely `n` and `$`)
- `{…}` iterators, as they depend on the amount of data remaining.
- Internal references (any `/1` or `/p1` types references)

### Struct

```python
Struct(format, names=None, safe_references=True)
```

Struct objects allow to pre-parse format strings once and for all.
Indeed, using only format strings will force to parse them every time you use them.
If a structure is used more than once, it will thus save time to wrap it in a Struct object.
You can also set the element names once, they will then be used by default every time you unpack data with that structure.
Any function that accepts a format string also accepts Struct objects.
A Struct object is initialized with a format string, and can take a `names` parameter that may be a namedtuple or a list of names, that allows to return data unpacked with this structure in a more convenient namedtuple. The `safe_references`, when set to `False`, allows some seemingly unsafe but sometimes desirable behaviours described in the *References* section.
It works exactly the same as the `names` parameter of `unpack` and its variants, but without having to specify it each time.
For convenience, Struct also defines the module-level functions, for the structure it represents (without the `structure` argument as it is for the represented structure) :

```python
unpack(self, data, names=None, refdata=())
unpack_from(self, data, offset=None, names=None, refdata=(), getptr=False)
iter_unpack(self, data, names=None, refdata=())
pack(self, *data, refdata=())
pack_into(self, buffer, offset, *data, refdata=())
pack_file(self, file, *data, position=None, refdata=())
calcsize(self, refdata=None, tokens=None)
```

You can retrieve the byte order with the `byteorder` attribute (can be `"little"` or `"big"`), and the format string (without byte order mark) with the `format` attribute.
You can also tell whether the structure has an assigned byte order with the `forcebyteorder` attribute.

It is also possible to add structures (it can add Struct and format strings transparently), and multiply a Struct object :

```python
>>> part1 = Struct("<4s")
>>> part2 = Struct("I /0(#0B #0b)")
>>> part3 = "I /0s #0a"
>>> part1 + part2 + part3
Struct("<4s I /1(#0B #0b) I /3s #1a")
>>> part2 * 3
Struct("<I /0(#0B #0b) I /2(#1B #1b) I /4(#2B #2b)")
```
As you can see, the references are automatically fixed : all absolute references in the resulting structure point on the element they pointed to previously.
External references are fixed too, and supposed to be in sequence in `refdata`.

Note that if the added structures have different byte order marks, the resulting structure will always retain the byte order of the left operand.

### Exceptions

Rawutil defines several exception types :

- `rawutil.FormatError` : Raised when the format string parsing fails, or if the structure is invalid
- `rawutil.OperationError` : Raised when operations on data fail
	- `rawutil.DataError` : Raised when data is at fault (e.g. when there is not enough data to unpack the entire format)


It also uses a few others :

- `OverflowError` : When the data is out of range for its format

## Format strings

In the same way as the `struct` module, binary data structures are defined with **format strings**.

### Byte order marks

The first character of the format string may be used to specify the byte order to read the data in.
Those are the same as in `struct`, except `@` that is equivalent to `=` instead of setting native sizes and alignments.

| Chr. | Description |
| ---- | ----------- |
| =    | System byte order (as defined by sys.byteorder) |
| @    | Equivalent to =, system byte order |
| >    | Big endian (most significant byte first) |
| <    | Little endian (least significant byte first) |
| !    | Network byte order (big endian as defined by RFC 1700 |

If no byte order is defined in a structure, it is set to system byte order by default.

### Elements

There are several format characters, that define various data types. Simple data types are described in the following table :

| Chr. | Type   | Size | Description |
| ---- | ------ | ---- | ----------- |
| ?    | bool   | 1    | Boolean value, 0 for False and any other value for True (packed as 0 and 1) |
| b    | int8   | 1    | 8 bits signed integer (7 bits + 1 sign bit) |
| B    | uint8  | 1    | 8 bits unsigned integer |
| h    | int16  | 2    | 16 bits signed integer |
| H    | uint16 | 2    | 16 bits unsigned integer |
| u    | int24  | 3    | 24 bits signed integer |
| U    | uint24 | 3    | 24 bits unsigned integer |
| i    | int32  | 4    | 32 bits signed integer |
| I    | uint32 | 4    | 32 bits unsigned integer |
| l    | int32  | 4    | 32 bits signed integer (same as `i`) |
| L    | uint32 | 4    | 32 bits unsigned integer (same as `I`) |
| q    | int64  | 8    | 64 bits signed integer |
| Q    | uint64 | 8    | 64 bits unsigned integer |
| e    | half   | 2    | IEEE 754 half-precision floating-point number |
| f    | float  | 4    | IEEE 754 single-precision floating-point number |
| d    | double | 8    | IEEE 754 double-precision floating-point number |
| F    | quad   | 16   | IEEE 754 quadruple-precision floating-point number |
| c    | char   | 1    | Character (returned as a 1-byte bytes object) |
| x    | void   | 1    | Convenience padding byte. Takes no data to pack (it simply inserts a null byte) nor returns anything. **Does not fail** when there is no more data to read. To fail in that case, just use a normal `c` |

A number before a simple format character may be added to indicate a repetition : `"4I"` means four 32-bits unsigned integers, and is equivalent to `"IIII"`.

There also exist "special" format characters that define more complex types and behaviours :

| Chr. | Type   | Description |
| ---- | ------ | ----------- |
| s    | char[] | Fixed-length string. Represents a string of a given length, for example `"16s"` represents a 16-byte string. Returned as a single `bytes` object (as a contrary to `c` that only returns individual characters) |
| n    | string | Null-terminated string. To unpack, reads until a null byte is found and returns the result as a `bytes` object, without the null byte. Packs the given bytes, and adds a null byte at the end.
| X    | hex    | Works like `s`, but returns the result as an hexadecimal string. |
| a    |        | Inserts null bytes / reads until the data length reaches the next multiple of the given number (for example, `"4a"` goes to the next multiple of 4). Does not return anything and does not take input data to pack. |
| $    | char[] | When unpacking, returns all remaining data as a bytes object. When packing, simply packs the given bytes object. Must be the last element of the structure. |

You can also set the base position for alignment with the `|` character. An alignment will then be performed according to the latest `|`.
For example, `"QBBB 4a"` represents 1 uint64, 3 bytes and one alignment byte to get to the next multiple of 4 (12), whereas `"QB| BB 4a"` will align according to the `|` and give 1 uint64, 3 bytes and 2 alignment bytes, to get to 4 bytes since the last `|`.

Note that `$` must be at the end of the structure. Any other element after a `$` element will cause a `FormatError`

## References

One of the biggest additions of rawutil is references.
With rawutil, it is possible to use a value previously read as a repeat count for another element, and to insert custom values in a structure at run-time.

There are 3 types of references.

### External references

An external reference is a reference to a value given at run-time — namely through the `refdata` argument of all rawutil functions
In the format string, those are denoted by a `#n` element, with the index in `refdata` as `n`.
For example, in the structure `"#0B #1s"`, `#0` will be replaced by the element 0 of `refdata`, and `#1` by the element 1.

Example :
```python
>>> unpack("#0B #1s", b"\x01\x02\x03foobar", refdata=(3, 6))
[1, 2, 3, b'foobar']
```

In the case above, it is equivalent to have `"3B 6s"` as the structure — but when you have to use several times the same structures with different repeat counts, it is possible to pre-compile the structure in a Struct object with external references, and then use the same object every time with different value, and without re-parsing the structure each time.

### Absolute references

Absolute references allow to use a value previously read as a repeat count for another element further in the structure.
Those are denoted with `/N`, with the index of the referenced element in the structure as `N`.
For example, in the structure `"I /0s"`, the integer is used to tell the length of the string, and the reference allows to read the string with that length.
For absolute and relative references, a sub-structure counts for 1 element.

Example :
```python
>>> unpack("3B /0s /1s /2s", b"\x04\x03\x04spamhameggs")
[4, 3, 4, b'spam', b'ham', b'eggs']
```

### Relative references

Relative references are similar to absolute references, except that they are relative to their location in the structure.
They are denoted with `/pN`, where `N` is the number of elements to go back in the structure to find the referenced element.
It works a bit like negative list indices in Python : `/p1` gives the immediately previous element, `/p2` the one before, and so on.

Example :
```python
>>> unpack("B /p1s 2B /p2s /p2s", b"\x04spam\x03\x04hameggs")
[4, b'spam', 3, 4, b'ham', b'eggs']
```

This is especially useful in cases where there are a variable amount of elements before the referenced element, when the absolute references are unpractical — or when the structure is very long and absolute references become less practical.

### Reference error checking

References come with some error checking : errors are caught while parsing the format when possible. For instance, a reference that points to itself, an element beyond itself, or before the beginning of the format is invalid. Those errors raise a `FormatError`. However, even though it is quite unsafe to reference an element inside or beyond a part with an indeterminate amount of elements (typically, another reference), but that might be useful sometimes. Those "unsafe behaviours" are disabled by default : you need to use `Struct()` with argument `safe_references=False` to activate them.

```python
>>> # For instance, here we reference the last element of the first block, that itself uses a reference
>>> unpack("B /0B /p1c", b"\x02\xFF\x03ABC")
...
rawutil.FormatError: In format 'B /0B /p1c', in subformat 'B/0B/p1c', at position 4 : Unsafe reference index : relative reference references in or beyond an indeterminate amount of elements (typically a reference). If it is intended, use the parameter safe_references=False of the Struct() constructor
>>> Struct("B /0B /p1c", safe_references=False).unpack(b"\x02\xFF\x03ABC")
[2, 255, 3, b'A', b'B', b'C']
```

## Sub-structures

The other big addition in rawutil is the substructures elements.
Those can be used to isolate values in their own group instead of diluted in the global scope, or to easily read several times a similar group of structure elements. They can of course be nested.

Note that a substructure always count as a single element towards references, and that references are local to their group : a `/0` reference inside of a substructure will point to the first element *of that substructure*.

Alignments are also local to their substructure, thus will always align relative to the beginning of the substructure.

### Groups

A group is simply a group of values isolated in their own sub-list.
Those are defined between parentheses `(…)`.
The values in a group are then extracted in a sub-list, and must be in a sub-list when packed.

Example :
```python
>>> unpack("<I (3B) I", b"\xff\xff\xff\xff\x01\x02\x03\xff\xff\xff\xff")
[4294967295, [1, 2, 3], 4294967295]
>>> pack("<I (3B) I", 0xFFFFFFFF, (1, 2, 3), 0xFFFFFFFF)
b'\xff\xff\xff\xff\x01\x02\x03\xff\xff\xff\xff'
```

When a repeat count is set to a group (as a number or as a reference, both are always valid), it will extract the group several times, but in the same sub-list, as a contrary to iterators that are described below.

Example :
```python
>>> unpack("B 3(n)", b"\x0afoo\x00bar\x00foo2\x00")
[10, [b'foo', b'bar', b'foo2']]
>>> unpack("B /0(n)", b"\x03foo\x00bar\x00foo2\x00")
[3, [b'foo', b'bar', b'foo2']]
```

### Iterators

An iterator will extract its substructure as many times as it is told by its repeat count, in separate sub-lists.
It is defined between square brackets `[…]`

Example :
```python
>>> unpack("B /0[B /0s]", b"\x03\x03foo\x03bar\x06foobar")
[3, [[3, b'foo'], [3, b'bar'], [6, b'foobar']]]
>>> pack("B /0[B /0s]", 2, ((3, b"foo"), (3, b"bar")))
b'\x02\x03foo\x03bar'
```

### Unbound iterators

While `[]` iterators are more or less equivalent to a `for i in range(count)`, those are equivalent to a `while`.
This kind of iterator is defined between curly brackets `{…}`, and extracts its substructure into a list of lists just like `[]`, except that it extracts until there are no more data left to read.
Thus you must not give it any repeat count (doing so will throw a `FormatError`), and it must always be the last element of its structure (it also raises an exception otherwise).
The data to read must be an exact multiple of that substructure, otherwise it will throw an `OperationError` when attempting to unpack it.

Example :
```python
>>> unpack("4s {Bn}", b"TEST\x00\foo\x00\x01bar\x00\x02foobar\x00")
[b'TEST', [[0, b'\x0coo'], [1, b'bar'], [2, b'foobar']]]
>>> pack("4s {Hn4a}", b"TEST", ((1, b"foo"), (1295, b"bar")))
b'TEST\x01\x00foo\x00\x00\x00\x0f\x05bar\x00\x00\x00'
```
