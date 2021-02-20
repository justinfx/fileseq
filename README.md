# <img src="docs/_static/fileseq_large.png" width="30%" height="30%" title="Fileseq" alt="Fileseq">

[![Documentation Status](https://readthedocs.org/projects/fileseq/badge/?version=latest)](http://fileseq.readthedocs.io/en/latest/) [![Build status](https://github.com/justinfx/fileseq/actions/workflows/ci.yml/badge.svg)](https://github.com/justinfx/fileseq/actions/workflows/ci.yml)

A Python library for parsing frame ranges and file sequences commonly 
used in VFX and Animation applications.

## Frame Range Shorthand

Support for:

* Standard: 1-10
* Comma Delimited: 1-10,10-20
* Chunked: 1-100x5
* Filled: 1-100y5
* Staggered: 1-100:3 (1-100x3, 1-100x2, 1-100)
* Negative frame numbers: -10-100
* Subframes: 1001-1066x0.25, 1001.5-1066.0x0.5
* Padding: #=4 padded, @=1 padded
* Alternate padding: #=1 padded, @=1 padded
* Printf Syntax Padding: %04d=4 padded, %01d=1 padded
* Houdini Syntax Padding: $F4=4 padding, $F=1 padded

## FrameSets

A FrameSet wraps a sequence of frames in a list container.

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
fileseq.FileSequence("/foo/bar.1-10x0.25#.#.exr", allow_subframes=True)
```

### Format Path for VFX Software

#### Using FileSequence.format Method:
```python
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr")
>>> seq.format(template='{dirname}{basename}{padding}{extension}') 
"/foo/bar.#.exr"
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.#.exr", allow_subframes=True)
>>> seq.format(template='{dirname}{basename}{padding}{extension}')
"/foo/bar.#.#.exr"
```

#### Joining:
```python
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr")
>>> ''.join([seq.dirname(), seq.basename(), '%0{}d'.format(len(str(seq.end()))), seq.extension()])
"/foo/bar.%02d.exr"
```

#### Alternate Padding Styles:
```python
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr", pad_style=fileseq.PAD_STYLE_HASH1)
>>> list(seq)
['/foo/bar.1.exr',
 '/foo/bar.2.exr',
 '/foo/bar.3.exr',
 '/foo/bar.4.exr',
 '/foo/bar.5.exr',
 '/foo/bar.6.exr',
 '/foo/bar.7.exr',
 '/foo/bar.8.exr',
 '/foo/bar.9.exr',
 '/foo/bar.10.exr']
>>> seq = fileseq.FileSequence("/foo/bar.1-10#.exr", pad_style=fileseq.PAD_STYLE_HASH4)
>>> list(seq)
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

* To find subframe sequences you must explicitly opt-in
```python
fileseq.findSequenceOnDisk('/foo/bar.#.#.exr', allow_subframes=True)
```

## Language Ports

* Go: https://github.com/justinfx/gofileseq
* C++: https://github.com/justinfx/gofileseq/tree/master/cpp
