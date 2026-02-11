"""Parse result data structure from ANTLR visitor."""
from dataclasses import dataclass


@dataclass
class ParseResult:
    """
    Result of parsing a file path through ANTLR grammar.

    Exactly one of is_sequence, is_single_frame, or is_plain_file must be True.
    """

    # Parsed components
    directory: str = ""
    basename: str = ""
    frame_range: str = ""
    padding: str = ""
    extension: str = ""

    # Python-specific subframe support
    subframe_range: str = ""  # Optional second frame range for subframes (e.g., "10-20" from "1-5#.10-20@@")
    has_negative_zero: bool = False  # Track if negative zero frames are present

    # Type flags (mutually exclusive)
    is_sequence: bool = False      # Full sequence with padding: /path/file.1-100#.exr
    is_single_frame: bool = False  # Single frame file: /path/file.100.exr
    is_plain_file: bool = False    # No frame pattern: /path/file.txt

    def __post_init__(self):
        """Validate that exactly one type flag is set."""
        flags = [self.is_sequence, self.is_single_frame, self.is_plain_file]
        if sum(flags) != 1:
            raise ValueError(
                "Exactly one type flag must be True. "
                f"Got: is_sequence={self.is_sequence}, "
                f"is_single_frame={self.is_single_frame}, "
                f"is_plain_file={self.is_plain_file}"
            )
