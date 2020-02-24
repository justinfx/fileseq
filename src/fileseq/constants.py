#! /usr/bin/env python
"""
constants - General constants of use to fileseq operations.
"""
from __future__ import absolute_import

import re

# The max frame count of a FrameSet before a MaxSizeException
# exception is raised
MAX_FRAME_SIZE = 10000000
    
PAD_MAP = {"#": 4, "@": 1}

# Regular expression for matching a file sequence string.
# Example: /film/shot/renders/bilbo_bty.1-100#.exr
# Example: /film/shot/renders/bilbo_bty.1-100@.exr
# Example: /film/shot/renders/bilbo_bty.1-100@@@@#.exr
# Example: /film/shot/renders/bilbo_bty.1-100%04d.exr
# Example: /film/shot/renders/bilbo_bty.1-100$F4d.exr
SPLIT_PATTERN = r"""
    ((?:[-\d][-:,xy\d]*)?)  # range
    (                       # pad format
        [{0}]+              #   pad map characters
        |
        %(?:\d)*d           #   printf syntax pad format 
        |
        \$F(?:\d)*          #   Houdini syntax pad format
    )  
    """.format(''.join(PAD_MAP))
SPLIT_RE = re.compile(SPLIT_PATTERN, re.X)

# Regular expression pattern for matching padding against a printf syntax
# padding string E.g. %04d
PRINTF_SYNTAX_PADDING_PATTERN = r"^%(\d+)*d\Z"
PRINTF_SYNTAX_PADDING_RE = re.compile(PRINTF_SYNTAX_PADDING_PATTERN)

# Regular expression pattern for matching padding against houdini syntax
HOUDINI_SYNTAX_PADDING_PATTERN = r"\$F(\d)*\Z"
HOUDINI_SYNTAX_PADDING_RE = re.compile(HOUDINI_SYNTAX_PADDING_PATTERN)

# Regular expression pattern for matching file names on disk.
DISK_PATTERN = r"""
    ^
    ((?:.*[/\\])?)            # dirname
    (.*?)                     # basename
    (-?\d+)?                  # frame
    (                         # ext
        (?:\.\w*[a-zA-Z]\w)*  #   optional leading alnum ext prefix (.foo.1bar)
        (?:\.[^.]+)?          #   ext suffix
    )
    $
    """
DISK_RE = re.compile(DISK_PATTERN, re.X)

# Regular expression pattern for matching frame set strings.
# Examples: '1' or '1-100', '1-100x5', '1-100:5', '1-100y5', '1,2', etc.
FRANGE_PATTERN = r"""
    ^
    (-?\d+)             # start frame
    (?:                 # optional range
        -               #   range delimiter
        (-?\d+)         #   end frame
        (?:             #   optional stepping
            ([:xy]{1})  #     step format
            (-?\d+)     #     step value
        )?
    )?
    $
    """
FRANGE_RE = re.compile(FRANGE_PATTERN, re.X)

# Regular expression for padding a frame range.
PAD_PATTERN = r"""
    (-?)(\d+)           # start frame
    (?:                 # optional range
        (-)             #   range delimiter
        (-?)(\d+)       #   end frame
        (?:             #   optional stepping
            ([:xy]{1})  #     step format
            (\d+)       #     step value
        )?
    )?
    """
PAD_RE = re.compile(PAD_PATTERN, re.X)
