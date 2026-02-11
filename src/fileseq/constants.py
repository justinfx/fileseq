"""
fileseq constants module.

Defines constant values used throughout the fileseq package.
"""

import re
import typing

# The max frame count of a FrameSet before a MaxSizeException
# exception is raised
MAX_FRAME_SIZE = 10000000


class _PadStyle(object):
    def __init__(self, name: str):
        self.__name = name

    def __hash__(self) -> int:
        return hash(str(self))

    def __repr__(self) -> str:
        return '<PAD_STYLE: {}>'.format(self.__name)

    def __str__(self) -> str:
        return self.__name

    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, _PadStyle):
            return False
        return str(self) == str(other)


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

# Regular expression pattern for matching padding against a printf syntax
# padding string E.g. %04d
PRINTF_SYNTAX_PADDING_PATTERN = r"\A%(\d*)d\Z"
PRINTF_SYNTAX_PADDING_RE = re.compile(PRINTF_SYNTAX_PADDING_PATTERN)

# Regular expression pattern for matching padding against houdini syntax
HOUDINI_SYNTAX_PADDING_PATTERN = r"\A\$F(\d*)\Z"
HOUDINI_SYNTAX_PADDING_RE = re.compile(HOUDINI_SYNTAX_PADDING_PATTERN)

# Legal patterns for UDIM style padding
UDIM_PADDING_PATTERNS = ['<UDIM>', '%(UDIM)d']

# Regular expression pattern for matching frame set strings (FrameSet parsing).
# Note: Supports decimal frames for Python-specific subframe feature.
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

# ============================================================================
# Disk File Frame Extraction (NOT sequence pattern parsing)
# ============================================================================
# These patterns extract frame numbers from individual file paths on disk.
# The ANTLR grammar handles sequence PATTERN parsing (e.g., "file.1-100#.exr").
# These regex patterns handle DISK FILE matching (e.g., extracting "1000" from "bar1000.exr").
# Aligned with Go's optionalFramePattern in fileseq.go
#
# Why both? The grammar requires explicit syntax (dots before frames, padding markers).
# Disk files lack this syntax - "bar1000.exr" is ambiguous (basename or frame?).
# These patterns extract frames from ambiguous filenames during disk scanning.

_EXT_PATTERN = r"""
    (?:\.\w*[a-zA-Z]\w?)*  # optional leading alnum ext prefix (limit trailing chars)
    (?:\.[^.]+)?           # ext suffix
"""

# DISK_RE: Extract frames from disk files (integers only, aligned with Go)
DISK_PATTERN = r"""
    \A
    ((?:.*[/\\])?)         # dirname
    (.*?)                  # basename (non-greedy)
    (-?\d+)?               # frame (optional, integers only)
    (""" + _EXT_PATTERN + r""")
    \Z
"""
DISK_RE = re.compile(DISK_PATTERN, re.X)

# DISK_SUB_RE: Python-specific variant with subframe support (decimal frames)
DISK_SUB_PATTERN = r"""
    \A
    ((?:.*[/\\])?)         # dirname
    (.*?)                  # basename (non-greedy)
    (-?\d+(?:\.\d+)?)?     # frame with subframe support (decimal)
    (""" + _EXT_PATTERN + r""")
    \Z
"""
DISK_SUB_RE = re.compile(DISK_SUB_PATTERN, re.X)
