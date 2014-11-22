Fileseq
=======

A Python library for parsing frame ranges and file sequences based on a similar library found in Katana.

Frame Range Shorthand
=====================

Support for:

* Standard: 1-10
* Comma Delimted: 1-10,10-20
* Chunked: 1-100x5
* Filled: 1-100y5
* Staggered: 1-100:3 (1-100x3, 1-100x2, 1-100)
* Negative frame numbers: -10-100
* Padding: #=4 padded, @=single pad

FrameSets
=========

A FrameSet wraps a sequence of frames in a list list container.

Iterate a FrameSet
------------------

```
fs = fileseq.FrameSet("1-5")
for f in fs:
  print f
```

Random Access
-------------

```
fs = fileseq.FrameSet("1-100:8")
print fs[-1] # Print last frame
```

FileSequence
============

```
fileseq.FileSequence("/foo/bar.1-10#.exr")
```

Finding Sequences on Disk
=========================

```
seqs = fileseq.findSequencesOnDisk("/show/shot/renders/bty_foo/v1")
```

