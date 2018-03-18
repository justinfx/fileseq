#! /usr/bin/env python
"""
constants - General constants of use to fileseq operations.
"""

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
SPLIT_PATTERN = r"((?:[-\d][-:,xy\d]*)?)([{0}]+|%\d+d)".format(''.join(PAD_MAP.keys()))
SPLIT_RE = re.compile(SPLIT_PATTERN)

# Regular expression pattern for matching padding against a printf syntax
# padding string E.g. %04d
PRINTF_SYNTAX_PADDING_PATTERN = r"%(\d+)d"
PRINTF_SYNTAX_PADDING_RE = re.compile(PRINTF_SYNTAX_PADDING_PATTERN)

# Regular expression pattern for matching file names on disk.
DISK_PATTERN = r"^((?:.*[/\\])?)(.*?)(-?\d+)?((?:\.\w*[a-zA-Z]\w)*(?:\.[^.]+)?)$"
DISK_RE = re.compile(DISK_PATTERN)

# Regular expression pattern for matching frame set strings.
# Examples: '1' or '1-100', '1-100x5', '1-100:5', '1-100y5', '1,2', etc.
FRANGE_PATTERN = r"^(-?\d+)(?:-(-?\d+)(?:([:xy]{1})(\d+))?)?$"
FRANGE_RE = re.compile(FRANGE_PATTERN)

# Regular expression for padding a frame range.
PAD_PATTERN = r"(-?)(\d+)(?:(-)(-?)(\d+)(?:([:xy]{1})(\d+))?)?"
PAD_RE = re.compile(PAD_PATTERN)
