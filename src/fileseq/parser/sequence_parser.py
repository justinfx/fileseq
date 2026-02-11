"""
High-level sequence parsing using ANTLR4 grammar.

This module provides the parsing logic for FileSequence initialization.
"""
from __future__ import annotations

import os
from typing import NamedTuple

from .parse import parse_file_sequence


class SeqParseResult(NamedTuple):
    """Result of parsing a sequence string."""
    directory: str
    basename: str
    frame_range: str | None
    padding: str
    extension: str
    has_negative_zero: bool
    subframe_range: str = ""  # Python-specific: second frame range for dual-range subframes
    is_single_frame: bool = False  # True for singleFrame grammar rule (auto-padding applies)


def parse_sequence_string(
    sequence: str,
    allow_subframes: bool = False
) -> SeqParseResult:
    """
    Parse a sequence string using ANTLR4 grammar.

    Args:
        sequence: The sequence string to parse (e.g., "/path/file.1-100#.exr")
        allow_subframes: Whether to allow subframe notation

    Returns:
        SeqParseResult with parsed components

    Raises:
        ValueError: If parsing fails
    """
    # Parse using ANTLR
    result = parse_file_sequence(sequence)

    # Check for negative zero in frame range (semantic check for formatting preference)
    # Grammar parses "-0" but can't know if user wants negative zero formatting
    has_negative_zero = '-0' in result.frame_range if result.frame_range else False

    return SeqParseResult(
        directory=result.directory,
        basename=result.basename,
        frame_range=result.frame_range if result.frame_range else None,
        padding=result.padding,
        extension=result.extension,
        has_negative_zero=has_negative_zero,
        subframe_range=result.subframe_range,
        is_single_frame=result.is_single_frame,
    )
