#! /usr/bin/env python
"""
constants - General constants of use to fileseq operations.
"""
from __future__ import absolute_import

import re

# The max frame count of a FrameSet before a MaxSizeException
# exception is raised
MAX_FRAME_SIZE = 10000000


class _PadStyle(object):
    def __init__(self, name): self.__name = name
    def __repr__(self): return '<PAD_STYLE: {}>'.format(self.__name)

PAD_STYLE_HASH1 = _PadStyle("HASH1")
PAD_STYLE_HASH4 = _PadStyle("HASH4")
PAD_STYLE_DEFAULT = PAD_STYLE_HASH4

PAD_MAP = {
    "#": {PAD_STYLE_HASH1: 1, PAD_STYLE_HASH4: 4},
    "@": {PAD_STYLE_HASH1: 1, PAD_STYLE_HASH4: 1}
}

# Map width back to preferred padding character. Every pad style must have an
# entry for width 1, which will also be the default pad character
REVERSE_PAD_MAP = {
    PAD_STYLE_HASH1: {1: "#"},
    PAD_STYLE_HASH4: {1: "@", 4: "#"}
}

# Component of SPLIT_PATTERN (c.f FRANGE_PATTERN).
_FRANGE_PART = r"""
    -?\d+           # start frame
    (?:             # optional range
        -           #   range delimiter
        -?\d+       #   end frame
        (?:         #   optional stepping
            [:xy]   #     step format
            -?\d+   #     step value
        )?
    )?
"""
_FRANGE_PART = re.compile(_FRANGE_PART, re.X).pattern

# Regular expression for matching a file sequence string.
# Example: /film/shot/renders/bilbo_bty.1-100#.exr
# Example: /film/shot/renders/bilbo_bty.1-100@.exr
# Example: /film/shot/renders/bilbo_bty.1-100@@@@#.exr
# Example: /film/shot/renders/bilbo_bty.1-100%04d.exr
# Example: /film/shot/renders/bilbo_bty.1-100$F4d.exr
SPLIT_PATTERN = r"""
    ((?:{0}(?:,{0})*)?)     # range
    (                       # pad format
        [{1}]+              #   pad map characters
        |
        %\d*d               #   printf syntax pad format
        |
        \$F\d*              #   Houdini syntax pad format
    )
    """.format(_FRANGE_PART, ''.join(PAD_MAP))
SPLIT_RE = re.compile(SPLIT_PATTERN, re.X)

# Component of SPLIT_SUB_PATTERN (c.f FRANGE_PATTERN).
# If both start and stop are present either both or neither should have
# a fractional component to avoid ambiguity when basename ends in \d\.
_FRANGE_SUB_PARTS = [
    _FRANGE_PART,
    r"""
    (?:
        -?\d+                     # start frame
        (?:                       # optional range
            -                     #   range delimiter
            -?\d+                 #   end frame
            (?:                   #   optional stepping
                x                 #     step format
                -?\d+\.\d+        #     step value
            )?
        )?
    )
    """,r"""
    (?:
        -?\d+\.\d+                # start frame
        (?:                       # optional range
            -                     #   range delimiter
            -?\d+\.\d+            #   end frame
            (?:                   #   optional stepping
                x                 #     step format
                -?\d+(?:\.\d+)?   #     step value
            )?
        )?
    )
"""]
_FRANGE_SUB_PARTS = [
    re.compile(part, re.X).pattern for part in _FRANGE_SUB_PARTS
]

# Regular expression for matching a file sequence string allowing subframes.
# Example: /film/shot/renders/bilbo_bty.1-100#.#.exr
# Example: /film/shot/renders/bilbo_bty.1.5-2x0.1#.#.exr
SPLIT_SUB_PATTERN = r"""
    (                         # range
        (?:
            (?:{1}(?:,{1})*)
            |
            (?:{2}(?:,{2})*)
            |
            (?:{3}(?:,{3})*)
        )?
    )
    (                         # pad format
        [{0}]+(?:\.[{0}]+)?   #   pad map characters
        |
        %\d*d                 #   printf syntax pad format
        |
        \$F\d*                #   Houdini syntax pad format
    )
    """.format(''.join(PAD_MAP), *_FRANGE_SUB_PARTS)
SPLIT_SUB_RE = re.compile(SPLIT_SUB_PATTERN, re.X)

# Regular expression pattern for matching padding against a printf syntax
# padding string E.g. %04d
PRINTF_SYNTAX_PADDING_PATTERN = r"\A%(\d*)d\Z"
PRINTF_SYNTAX_PADDING_RE = re.compile(PRINTF_SYNTAX_PADDING_PATTERN)

# Regular expression pattern for matching padding against houdini syntax
HOUDINI_SYNTAX_PADDING_PATTERN = r"\A\$F(\d*)\Z"
HOUDINI_SYNTAX_PADDING_RE = re.compile(HOUDINI_SYNTAX_PADDING_PATTERN)

# Regular expression pattern for matching file names on disk.
DISK_PATTERN = r"""
    \A
    ((?:.*[/\\])?)            # dirname
    (.*?)                     # basename
    (-?\d+)?                  # frame
    (                         # ext
        (?:\.\w*[a-zA-Z]\w)*  #   optional leading alnum ext prefix (.foo.1bar)
        (?:\.[^.]+)?          #   ext suffix
    )
    \Z
    """
DISK_RE = re.compile(DISK_PATTERN, re.X)

# Regular expression pattern for matching file names on disk allowing subframes.
DISK_SUB_PATTERN = r"""
    \A
    ((?:.*[/\\])?)            # dirname
    (.*?)                     # basename
    (-?\d+(?:\.\d+)?)?        # frame
    (                         # ext
        (?:\.\w*[a-zA-Z]\w)*  #   optional leading alnum ext prefix (.foo.1bar)
        (?:\.[^.]+)?          #   ext suffix
    )
    \Z
    """
DISK_SUB_RE = re.compile(DISK_SUB_PATTERN, re.X)

# Regular expression pattern for matching frame set strings.
# Examples: '1.0' or '1.0-100.0', '1.0-100.0x0.5', '1-100x0.25',
# '1,2', etc.
FRANGE_PATTERN = r"""
    \A
    (-?\d+(?:\.\d+)?)         # start frame
    (?:                       # optional range
        -                     #   range delimiter
        (-?\d+(?:\.\d+)?)     #   end frame
        (?:                   #   optional stepping
            ([:xy])           #     step format
            (-?\d+(?:\.\d+)?) #     step value
        )?
    )?
    \Z
    """
FRANGE_RE = re.compile(FRANGE_PATTERN, re.X)

# Regular expression for padding a frame range.
PAD_PATTERN = r"""
    (-?)(\d+(?:\.\d+)?)     # start frame
    (?:                     # optional range
        (-)                 #   range delimiter
        (-?)(\d+(?:\.\d+)?) #   end frame
        (?:                 #   optional stepping
            ([:xy])         #     step format
            (\d+(?:\.\d+)?) #     step value
        )?
    )?
    """
PAD_RE = re.compile(PAD_PATTERN, re.X)
