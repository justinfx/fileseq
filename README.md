Fileseq
=======

A Python library for parsing frame ranges and file sequences.

Frame Range Shorthand
=====================

Support for:

* Standard: 1-10
* Comma Delimted: 1-10,10-20
* Chunked: 1-100x5
* Filled: 1-100y5
* Staggered: 1-100:3 (1-100x3, 1-100x2, 1-100)
* Negative frame numbers: -10-100

FrameSets
=========

A FrameSet wraps a sequence of frames in a list list container.

Iterate a FrameSet
------------------

`
fs = fileseq.FrameSet("1-5")
>>> for f in fs:
...     print f
... 
1
2
3
4
5
`

Random Access
-------------

`
fs = fileseq.FrameSet("1-100:8")
# print last frame
print fs[-1]
`












