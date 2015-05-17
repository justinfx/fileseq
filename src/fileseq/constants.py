#! /usr/bin/env python
"""
constants - General constants of use to fileseq operations.
"""

import re

PAD_MAP = {"#": 4, "@": 1}

# Regular expression for matching a file sequence string.
# Example: /film/shot/renders/bilbo_bty.1-100#.exr
SPLIT_PATTERN = r"([-:,xy\d]*)([{0}]+)".format(''.join(PAD_MAP.keys()))
SPLIT_RE = re.compile(SPLIT_PATTERN)

# Regular expression pattern for matching file names on disk.
DISK_PATTERN = r"^(.*/)?(?:$|(.*?)(-?\d+)?(?:(\.[^.]*$)|$))"
DISK_RE = re.compile(DISK_PATTERN)

# Regular expression pattern for matching frame set strings.
# Examples: '1' or '1-100', '1-100x5', '1-100:5', '1-100y5', '1,2', etc.
FRANGE_PATTERN = r"^(-?\d+)(?:-(-?\d+)(?:([:xy]{1})(\d+))?)?$"
FRANGE_RE = re.compile(FRANGE_PATTERN)

# Regular expression for padding a frame range.
PAD_PATTERN = r"(-?)(\d+)(?:(-)(-?)(\d+)(?:([:xy]{1})(\d+))?)?"
PAD_RE = re.compile(PAD_PATTERN)
