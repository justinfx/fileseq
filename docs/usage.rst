Usage Guide
===========

This guide covers practical usage of the two main classes — :class:`~fileseq.FrameSet` and
:class:`~fileseq.FileSequence` — as well as the filesystem discovery functions and how to
extend the library through subclassing.

FrameSet
--------

A :class:`~fileseq.FrameSet` holds an ordered, deduplicated set of frame numbers parsed from a
range string.  It behaves like an immutable sequence and supports set-algebra operators.

**Range syntax**

.. code-block:: python

    from fileseq import FrameSet

    FrameSet('1-10')          # 1, 2, 3, …, 10
    FrameSet('1-10x2')        # step: 1, 3, 5, 7, 9
    FrameSet('1-10y2')        # fill (inverse step): 2, 4, 6, 8, 10
    FrameSet('1-10:3')        # stagger: 1-10x3, 1-10x2, 1-10
    FrameSet('-5-5')          # negative frames: -5, -4, …, 5
    FrameSet('1-5,10-20')     # comma-separated ranges

**Constructing from iterables or a single frame**

.. code-block:: python

    FrameSet([1, 2, 3, 4, 5])
    FrameSet(42)              # single frame
    FrameSet(FrameSet('1-5')) # copy constructor

**Subframe support**

Pass ``Decimal`` values or a subframe range string to work with fractional frame numbers:

.. code-block:: python

    from fileseq import FrameSet

    FrameSet('1-3x0.5')          # 1.0, 1.5, 2.0, 2.5, 3.0
    FrameSet([0, 0.25, 0.5, 1])  # from an iterable of floats

**Iteration and indexing**

.. code-block:: python

    fs = FrameSet('1-10x2')

    list(fs)    # [1, 3, 5, 7, 9]
    fs[0]       # 1
    fs[-1]      # 9
    len(fs)     # 5
    5 in fs     # True

**Set operations**

.. code-block:: python

    a = FrameSet('1-5')
    b = FrameSet('3-7')

    a | b  # union:        1-7
    a & b  # intersection: 3-5
    a - b  # difference:   1-2
    a ^ b  # symmetric difference: 1-2, 6-7

**String representation**

.. code-block:: python

    str(FrameSet('1-10x2'))          # '1-9x2'
    FrameSet('1-5,10-20').frameRange # '1-5,10-20'

FileSequence
------------

A :class:`~fileseq.FileSequence` represents a path pattern paired with a frame range and a
padding token.

**Pattern syntax**

.. code-block:: text

    /path/to/name.{framerange}{padding}.ext

Supported padding tokens:

===========  ========================================================
Token        Width
===========  ========================================================
``#``        4 digits (``%04d``)
``@@@@``     4 digits
``@``        1 digit
``%04d``     printf-style (any width)
``$F4``      Houdini-style (any width)
``<UDIM>``   UDIM tile identifier (no padding)
===========  ========================================================

**Basic construction**

.. code-block:: python

    from fileseq import FileSequence

    seq = FileSequence('/render/beauty.1-100#.exr')
    print(seq.basename())    # 'beauty'
    print(seq.extension())   # '.exr'
    print(seq.padding())     # '#'
    print(seq.frameRange())  # '1-100'

**Accessing individual frames**

.. code-block:: python

    seq = FileSequence('/render/beauty.1-10#.exr')

    seq.frame(1)    # '/render/beauty.0001.exr'
    seq[0]          # first frame path (same as seq.frame(seq.start()))
    list(seq)       # all 10 file paths as strings

**Alternative padding styles**

.. code-block:: python

    FileSequence('/render/beauty.1-10@@@.exr')    # 3-digit padding
    FileSequence('/render/beauty.1-10%04d.exr')   # printf-style
    FileSequence('/render/beauty.1-10$F4.exr')    # Houdini-style

**Non-frame files**

A sequence with no frame range is valid:

.. code-block:: python

    seq = FileSequence('/render/config.json')
    seq.frameRange()  # ''
    seq.frame('')     # '/render/config.json'

**Pad style — HASH4 (default) vs HASH1 (ie Houdini)**

.. code-block:: python

    from fileseq import FileSequence, PAD_STYLE_DEFAULT, PAD_STYLE_HASH1

    # Default: '#' maps to 4-digit zero-padded
    seq = FileSequence('/out/f.1-10#.exr', pad_style=PAD_STYLE_DEFAULT)

    # Hash1: '#' maps to 1 digit, '####' to 4 digits (Houdini convention)
    seq = FileSequence('/out/f.1-10#.exr', pad_style=PAD_STYLE_HASH1)

**Subframe sequences**

Subframe support in a sequence pattern must be explicitly enabled, to avoid ambiguous parsing:

.. code-block:: python

    seq = FileSequence('/render/beauty.1-2x0.5#.#.exr', allow_subframes=True)
    list(seq)
    # ['/render/beauty.0001.0000.exr',
    #  '/render/beauty.0001.5000.exr',
    #  '/render/beauty.0002.0000.exr']

**Formatting**

:meth:`~fileseq.FileSequence.format` accepts a template string with named fields:

.. code-block:: python

    seq = FileSequence('/show/shot/beauty.1-100#.exr')
    seq.format('{dirname}{basename}{range}{padding}{extension}')
    # '/show/shot/beauty.1-100#.exr'

    seq.format('{basename}{extension}')  # 'beauty.exr'

**pathlib variant**

:class:`~fileseq.FilePathSequence` is identical to :class:`~fileseq.FileSequence` but returns
:class:`pathlib.Path` objects from iteration and :meth:`frame`:

.. code-block:: python

    from fileseq import FilePathSequence

    seq = FilePathSequence('/render/beauty.1-10#.exr')
    type(seq.frame(1))  # <class 'pathlib.PosixPath'>

Filesystem Discovery
--------------------

Three class methods locate sequences on disk.

**findSequencesOnDisk** — scan a directory

.. code-block:: python

    from fileseq import FileSequence

    # All sequences in a directory
    seqs = FileSequence.findSequencesOnDisk('/show/shot/renders/v001')
    for s in seqs:
        print(s)

    # Include hidden files (names starting with '.')
    seqs = FileSequence.findSequencesOnDisk('/renders', include_hidden=True)

    # Strict padding: only match files whose digit count equals the padding token width
    seqs = FileSequence.findSequencesOnDisk('/renders', strictPadding=True)

    # Subframe sequences
    seqs = FileSequence.findSequencesOnDisk('/renders', allow_subframes=True)

**findSequenceOnDisk** — find one specific sequence

.. code-block:: python

    # Wildcard padding: accepts any number of digits
    seq = FileSequence.findSequenceOnDisk('/renders/beauty.@.exr')

    # Strict padding: only files that match the token width exactly
    seq = FileSequence.findSequenceOnDisk('/renders/beauty.%04d.exr', strictPadding=True)

    # Preserve the original padding token in the result
    seq = FileSequence.findSequenceOnDisk('/renders/beauty.%02d.exr',
                                          strictPadding=True,
                                          preserve_padding=True)

**Using a custom subclass with the find methods**

All three find methods are classmethods, so the simplest way to get results of a
custom subclass is to call the method directly on that subclass.  The
``_preprocess_sequence`` and ``_postprocess_sequence`` hooks are picked up
automatically:

.. code-block:: python

    # Call directly on the subclass — hooks are used automatically
    seqs = VRayFileSequence.findSequencesOnDisk('/renders')
    seq  = VRayFileSequence.findSequenceOnDisk('/renders/beauty.<frame04>.exr',
                                               strictPadding=True,
                                               preserve_padding=True)
    seqs = VRayFileSequence.findSequencesInList(paths)

When the call site cannot be changed — for example in a generic utility that
always calls ``FileSequence.findSequenceOnDisk`` — pass the subclass via the
``klass`` argument instead:

.. code-block:: python

    # klass overrides which class is used to construct results
    seqs = FileSequence.findSequencesOnDisk('/renders', klass=VRayFileSequence)
    seq  = FileSequence.findSequenceOnDisk('/renders/beauty.<frame04>.exr',
                                           strictPadding=True,
                                           preserve_padding=True,
                                           klass=VRayFileSequence)
    seqs = FileSequence.findSequencesInList(paths, klass=VRayFileSequence)

Both approaches produce identical results.

**findSequencesInList** — build sequences from an existing file list in memory

This is useful when you already have a list of paths (e.g. from an asset database) and do not
want a directory scan:

.. code-block:: python

    paths = [
        '/renders/beauty.0001.exr',
        '/renders/beauty.0002.exr',
        '/renders/beauty.0003.exr',
        '/renders/hero.0001.exr',
    ]
    seqs = FileSequence.findSequencesInList(paths)
    # Returns two FileSequence objects: beauty.1-3#.exr and hero.0001#.exr

Normally each path is parsed through the grammar to identify its dirname, basename, extension,
and frame number.  When you already know that all paths share the same structure, pass a
``using`` template to skip that per-path parsing.  The template's dirname, basename, and
extension are used to compute character offsets, so the frame number is extracted by a plain
string slice rather than a full parse.  This can be significantly faster when the list is large:

.. code-block:: python

    # Without template: every path is parsed individually
    seqs = FileSequence.findSequencesInList(paths)

    # With template: frame extracted via string slicing — no per-path grammar parse
    template = FileSequence('/renders/beauty.#.exr')
    seqs = FileSequence.findSequencesInList(paths, using=template)

The template is also useful when the filename has an ambiguous structure — for example, a
basename that contains digits — and you want to pin exactly which numeric run is the frame
number:

.. code-block:: python

    paths = [
        '/renders/shot_101_beauty.0001.exr',
        '/renders/shot_101_beauty.0002.exr',
        '/renders/shot_101_beauty.0003.exr',
    ]
    # Without template, the '101' in the name could confuse sequence grouping.
    # The template makes the intent unambiguous:
    template = FileSequence('/renders/shot_101_beauty.#.exr')
    seqs = FileSequence.findSequencesInList(paths, using=template)
    # [<FileSequence: '/renders/shot_101_beauty.1-3#.exr'>]

Customizing with Subclasses
---------------------------

Both :class:`~fileseq.FileSequence` and :class:`~fileseq.FilePathSequence` inherit from the
abstract base :class:`~fileseq.filesequence.BaseFileSequence`.  You can subclass either to add
custom behaviour by overriding one or both hooks described below.

**_preprocess_sequence — translate custom syntax before parsing**

Override this method to accept sequence strings that use a non-standard notation.  The hook
receives the raw input string and must return a string in the grammar that fileseq understands.

VRay uses a ``<frameNN>`` token (e.g. ``<frame04>``) to express padding width.  This token is
not part of the fileseq grammar, but it maps cleanly to printf-style padding, so
``_preprocess_sequence`` is the right place to translate it:

.. code-block:: python

    import re
    import fileseq

    class VRayFileSequence(fileseq.FileSequence):
        """Translate VRay ``<frameNN>`` padding tokens to printf-style before parsing."""

        _VRAY_PAD_RE = re.compile(r'<frame(\d+)>')

        def _preprocess_sequence(self, sequence: str) -> str:
            def replace(m):
                width = int(m.group(1))
                return '%0{}d'.format(width) if width > 0 else '%d'
            return self._VRAY_PAD_RE.sub(replace, sequence)

    # With a frame range
    seq = VRayFileSequence('/render/beauty.1-100<frame04>.exr')
    seq.padding()     # '%04d'
    seq.frameRange()  # '0001-0100'
    seq.frame(42)     # '/render/beauty.0042.exr'

    # Pattern-only (no range embedded in the string)
    seq = VRayFileSequence('/render/beauty.<frame04>.exr')
    seq.padding()     # '%04d'
    seq.frameRange()  # ''

    # Subframe variant — two tokens, one for frames and one for the sub-second part
    seq = VRayFileSequence(
        '/render/beauty.1-5<frame04>.10-20<frame04>.exr',
        allow_subframes=True,
    )
    seq.frame(1)  # '/render/beauty.0001.0000.exr'

**_postprocess_sequence — restore custom syntax on output**

This is the complement to ``_preprocess_sequence``.  It is called by :meth:`~fileseq.FileSequence.__str__`
and :meth:`~fileseq.FileSequence.format` on the fully assembled sequence string just before it
is returned, giving subclasses the opportunity to translate internal grammar tokens back to the
original custom format.

Continuing the VRay example, adding ``_postprocess_sequence`` makes the class fully
round-trippable — the ``<frameNN>`` token survives both directions:

.. code-block:: python

    import re
    import fileseq

    class VRayFileSequence(fileseq.FileSequence):
        """Translate VRay ``<frameNN>`` padding tokens in both directions."""

        _VRAY_PAD_RE  = re.compile(r'<frame(\d+)>')
        _PRINTF_PAD_RE = re.compile(r'%0?(\d+)d')

        def _preprocess_sequence(self, sequence: str) -> str:
            def replace(m):
                width = int(m.group(1))
                return '%0{}d'.format(width) if width > 0 else '%d'
            return self._VRAY_PAD_RE.sub(replace, sequence)

        def _postprocess_sequence(self, sequence: str) -> str:
            def replace(m):
                return '<frame{:02d}>'.format(int(m.group(1)))
            return self._PRINTF_PAD_RE.sub(replace, sequence)

    seq = VRayFileSequence('/render/beauty.1-100<frame04>.exr')
    str(seq)    # '/render/beauty.1-100<frame04>.exr'
    seq.frame(42)  # '/render/beauty.0042.exr'  (frame paths are unaffected)

    # format() also passes through _postprocess_sequence
    seq.format('{dirname}{basename}{range}{padding}{extension}')
    # '/render/beauty.0001-0100<frame04>.exr'

Two things worth noting:

- ``_postprocess_sequence`` is **not** called by :meth:`~fileseq.FileSequence.frame` or
  iteration — only by the methods that produce a sequence pattern string.  Individual frame
  paths use the internal grammar padding (``%04d``) to resolve frame numbers correctly, so
  they are unaffected.
- :meth:`~fileseq.FileSequence.__str__` omits the padding token entirely when the sequence has
  no frame range.  For a pattern-only sequence, use :meth:`~fileseq.FileSequence.format` with
  an explicit ``{padding}`` field to get the round-tripped token back:

  .. code-block:: python

      seq = VRayFileSequence('/render/beauty.<frame04>.exr')
      str(seq)  # '/render/beauty..exr'  — padding omitted by str()
      seq.format('{dirname}{basename}{padding}{extension}')
      # '/render/beauty.<frame04>.exr'

**_create_path — control the type returned for each frame path**

Override this method to return a custom path type instead of a plain string.  The method
receives a fully-resolved path string and must return whatever object your code needs.

.. code-block:: python

    from pathlib import Path
    from fileseq import FileSequence

    class S3FileSequence(FileSequence):
        """Return S3-prefixed paths instead of local paths."""

        BUCKET = 's3://my-studio-bucket'

        def _create_path(self, path_str: str) -> str:
            # Strip the leading slash so the URL is well-formed
            return f'{self.BUCKET}/{path_str.lstrip("/")}'

    seq = S3FileSequence('/renders/beauty.1-3#.exr')
    seq.frame(1)  # 's3://my-studio-bucket/renders/beauty.0001.exr'
    list(seq)
    # ['s3://my-studio-bucket/renders/beauty.0001.exr',
    #  's3://my-studio-bucket/renders/beauty.0002.exr',
    #  's3://my-studio-bucket/renders/beauty.0003.exr']

Both hooks may be combined in a single subclass.
