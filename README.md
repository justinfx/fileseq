# Fileseq [![Documentation Status](https://readthedocs.org/projects/fileseq/badge/?version=latest)](http://fileseq.readthedocs.io/en/latest/) [![Travis Build Status](https://api.travis-ci.org/sqlboy/fileseq.svg)](https://travis-ci.org/sqlboy/fileseq) [![AppVeyor Build status](https://ci.appveyor.com/api/projects/status/87t3pycl3365lnkd?svg=true)](https://ci.appveyor.com/project/justinfx/fileseq)


A Python library for parsing frame ranges and file sequences based on a similar library found in Katana.

## Frame Range Shorthand

Support for:

* Standard: 1-10
* Comma Delimited: 1-10,10-20
* Chunked: 1-100x5
* Filled: 1-100y5
* Staggered: 1-100:3 (1-100x3, 1-100x2, 1-100)
* Negative frame numbers: -10-100
* Padding: #=4 padded, @=single pad
* Printf Syntax Padding: %04d=4 padded, %01d=1 padded

## FrameSets

A FrameSet wraps a sequence of frames in a list list container.

### Iterate a FrameSet
```python
fs = fileseq.FrameSet("1-5")
for f in fs:
  print f
```

### Access Frames

#### Using Indices:
```python
>>> fs = fileseq.FrameSet("1-100:8")
>>> fs[0] # First frame.
1
>>> fs[-1] # Last frame.
98
```

#### Using Convenience Methods:
```python
>>> fs = fileseq.FrameSet("1-100:8")
>>> fs.start() # First frame.
1
>>> fs.end() # Last frame.
98
```

## FileSequence

### Instantiate from String
```python
fileseq.FileSequence("/foo/bar.1-10#.exr")
```

### Format Path for VFX Software

#### Using FileSequence.format Method:
```python
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr")
>>> seq.format(template='{dirname}{basename}{padding}{extension}') 
"/foo/bar.#.exr"
```

#### Joining:
```python
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr")
>>> ''.join([seq.dirname(), seq.basename(), '%0{}d'.format(len(str(seq.end()))), seq.extension()])
"/foo/bar.%02d.exr"
```

### Get List of File Paths
```python
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr")
>>> [seq[idx] for idx, fr in enumerate(seq.frameSet())]
['/foo/bar.0001.exr',
 '/foo/bar.0002.exr',
 '/foo/bar.0003.exr',
 '/foo/bar.0004.exr',
 '/foo/bar.0005.exr',
 '/foo/bar.0006.exr',
 '/foo/bar.0007.exr',
 '/foo/bar.0008.exr',
 '/foo/bar.0009.exr',
 '/foo/bar.0010.exr']
```

## Finding Sequences on Disk

### Check a Directory for All Existing Sequences
```python
seqs = fileseq.findSequencesOnDisk("/show/shot/renders/bty_foo/v1")
```

### Check a Directory for One Existing Sequence.
* Use a '@' or '#' where you might expect to use '*' for a wildcard character. 
* For this method, it doesn't matter how many instances of the padding character you use, it will still find your sequence.

Yes:
```python
fileseq.findSequenceOnDisk('/foo/bar.@.exr')
```
Yes:
```python
fileseq.findSequenceOnDisk('/foo/bar.@@@@@.exr')
```
No: 
```python
fileseq.findSequenceOnDisk('/foo/bar.*.exr')
```

## Changes in versions >= 1.0.0

From version 1.0.0, a FrameSet allows all the normal Set operations.  It is now an immutable and
hashable object in its own right, as well.  This means that the order and contents are immutable
values internally (a tuple and a frozenset, respectively), and that the FrameSet itself can be
used as a key in a dictionary.

This also means that the null FrameSet (FrameSet('')) is a valid object, and something you should
expect to receive back from any Set operations that would result in an empty return value.  This
brings the caveat that the FrameSet.start and FrameSet.end methods on a null FrameSet will raise an
IndexError if called.

To help avoid confusion, a FrameSet.is_null attribute has been added in 1.0.1, which you can check 
before calling those methods.
