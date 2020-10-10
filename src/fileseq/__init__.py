"""
A Python library for parsing frame ranges and file sequences commonly
used in VFX and Animation applications.

The MIT License (MIT)

Original work Copyright (c) 2015 Matthew Chambers

Modified work Copyright 2015 Justin Israel

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

**Frame Range Shorthand**

Support for:

* Standard: 1-10
* Comma Delimited: 1-10,10-20
* Chunked: 1-100x5
* Filled: 1-100y5
* Staggered: 1-100:3 (1-100x3, 1-100x2, 1-100)
* Negative frame numbers: -10-100
* Subframes: 1001-1066x0.25
* Padding: #=4 padded, @=single pad
* Printf Syntax Padding: %04d=4 padded, %01d=1 padded
* Houdini Syntax Padding: $F4=4 padding, $F=1 padded

**FrameSets**

A :class:`~fileseq.frameset.FrameSet` wraps a sequence of frames in a list list container.

Iterate a FrameSet

.. doctest::

    >>> fs = FrameSet("1-5")
    >>> for f in fs:
    ...     print(f)
    1
    2
    3
    4
    5

Access Frames Using Indices

.. doctest::

    >>> fs = FrameSet("1-100:8")
    >>> fs[0] # First frame.
    1
    >>> fs[-1] # Last frame.
    98

Access Frames Using Convenience Methods:

.. doctest::

    >>> fs = FrameSet("1-100:8")
    >>> fs.start() # First frame.
    1
    >>> fs.end() # Last frame.
    98

**FileSequence**

A :class:`~fileseq.filesequence.FileSequence` is a container representing a filepath over a range of frames

Instantiate from string

.. doctest::

    >>> FileSequence("/foo/bar.1-10#.exr")
    <FileSequence: '/foo/bar.1-10#.exr'>

Format Path for VFX Software

*Using FileSequence.format Method*

.. doctest::

    >>> seq = FileSequence("/foo/bar.1-10#.exr")
    >>> seq.format(template='{dirname}{basename}{padding}{extension}')
    '/foo/bar.#.exr'
    >>> seq = FileSequence("/foo/bar.1-10#.#.exr", allow_subframes=True)
    >>> seq.format(template='{dirname}{basename}{padding}{extension}')
    '/foo/bar.#.#.exr'

*Joining*

.. doctest::

    >>> seq = FileSequence("/foo/bar.1-10#.exr")
    >>> seq.setPadding('%02d')
    >>> seq
    <FileSequence: '/foo/bar.1-10%02d.exr'>
    >>> seq.format(template='{dirname}{basename}{padding}{extension}')
    '/foo/bar.%02d.exr'

*Get List of File Paths*

.. doctest::

    >>> seq = FileSequence("/foo/bar.1-5#.exr")
    >>> list(seq)
    ['/foo/bar.0001.exr',
     '/foo/bar.0002.exr',
     '/foo/bar.0003.exr',
     '/foo/bar.0004.exr',
     '/foo/bar.0005.exr']
    >>> [seq[idx] for idx, fr in enumerate(seq.frameSet())]
    ['/foo/bar.0001.exr',
     '/foo/bar.0002.exr',
     '/foo/bar.0003.exr',
     '/foo/bar.0004.exr',
     '/foo/bar.0005.exr']

**Finding Sequences on Disk**

Check a Directory for All Existing Sequences

.. doctest::

    >>> seqs = findSequencesOnDisk("/show/shot/renders/bty_foo/v1")

Check a Directory for One Existing Sequence

* Use a '@' or '#' where you might expect to use '*' for a wildcard character.
* For this method, it doesn't matter how many instances of the padding character
  you use, it will still find your sequence (unless enabling strict padding option).

Yes:

.. code-block:: python

    findSequenceOnDisk('/foo/bar.@.exr')

Yes:

.. code-block:: python

    findSequenceOnDisk('/foo/bar.@@@@@.exr')

No:

.. code-block:: python

    findSequenceOnDisk('/foo/bar.*.exr')

* To find subframe sequences you must explicitly opt-in

.. code-block:: python

    fileseq.findSequenceOnDisk('/foo/bar.#.#.exr', allow_subframes=True)
"""
from __future__ import absolute_import

from fileseq.constants import PAD_STYLE_DEFAULT, PAD_STYLE_HASH1, PAD_STYLE_HASH4
from fileseq.exceptions import ParseException, MaxSizeException, FileSeqException
from fileseq.frameset import FrameSet
from fileseq.filesequence import FileSequence

padFrameRange = FrameSet.padFrameRange
framesToFrameRange = FrameSet.framesToFrameRange

getPaddingChars = FileSequence.getPaddingChars
getPaddingNum = FileSequence.getPaddingNum
findSequenceOnDisk = FileSequence.findSequenceOnDisk
findSequencesOnDisk = FileSequence.findSequencesOnDisk
findSequencesInList = FileSequence.findSequencesInList
