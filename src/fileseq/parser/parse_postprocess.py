"""
Post-processing for 3 special cases that can't be handled by grammar alone.
"""
import re
from .parse_result import ParseResult


def post_process(result: ParseResult) -> ParseResult:
    """
    Apply post-processing fixes for 3 special cases.

    1. Multiple DOT_NUM tokens (e.g., .10000000000.123)
    2. Extension tokens with trailing digits (e.g., .tmp12345@@@@@)
    3. Leading dot in frame range tokens (e.g., .1-100)

    Args:
        result: ParseResult from visitor

    Returns:
        Modified ParseResult with fixes applied
    """
    result = _fix_multiple_dot_num(result)
    result = _fix_extension_trailing_digits(result)
    result = _fix_leading_dot_in_frame_range(result)
    return result


def _fix_multiple_dot_num(result: ParseResult) -> ParseResult:
    """
    Special case 1: Handle basename ending with .digits when no extension.

    Example: /path/.10000000000.123
    - Parser sees: basename=".10000000000", extension=""
    - Grammar ambiguity: Both could be DOT_NUM tokens

    Fix: If basename ends with DOT_NUM pattern and extension is empty,
         swap them so frame number is extracted correctly.

    Result: basename=".10000000000", frame="(extracted)", extension=".123"
    """
    # Only applies to single frame files with no extension
    if not result.is_single_frame:
        return result

    if result.extension:
        return result  # Has extension, no fix needed

    # Check if basename ends with .digits pattern
    if not result.basename:
        return result

    # Pattern: ends with dot followed by digits
    match = re.search(r'(\.\d+)$', result.basename)
    if not match:
        return result

    # Split: everything before the .digits becomes basename,
    # .digits becomes extension
    dot_digits = match.group(1)
    result.basename = result.basename[:-len(dot_digits)]
    result.extension = dot_digits

    return result


def _fix_extension_trailing_digits(result: ParseResult) -> ParseResult:
    """
    Special case 2: Handle extension tokens that captured trailing digits.

    Example: /dir/f.tmp12345@@@@@
    - Parser sees: basename="f.tmp12345", padding="@@@@@"
    - EXTENSION token greedily matched ".tmp12345"

    Fix: Extract trailing digits from basename/extension as frame number.

    Result: basename="f.tmp", frame="12345", padding="@@@@@"
    """
    # Only applies to sequences (not single frames or plain files)
    if not result.is_sequence:
        return result

    # Only when we have padding but no explicit frame range
    if result.frame_range or not result.padding:
        return result

    # Check if basename ends with digits
    if not result.basename:
        return result

    match = re.search(r'(\d+)$', result.basename)
    if not match:
        return result

    # Extract digits as frame number
    digits = match.group(1)
    result.basename = result.basename[:-len(digits)]
    result.frame_range = digits

    return result


def _fix_leading_dot_in_frame_range(result: ParseResult) -> ParseResult:
    """
    Special case 3: Move leading dot from frame range to basename.

    Example (sequence): /path/file.1-100#.exr
    - Parser sees: frameRange=".1-100" (DOT_FRAME_RANGE token)
    - Result: basename="file.", frameRange="1-100"

    Example (single frame): /path/file.0000.exr
    - Parser sees: frameRange=".0000" (DOT_NUM token)
    - Result: basename="file.", frameRange="0000"

    This allows String() method to correctly output by concatenating:
    basename + frameRange + padding + extension
    """
    # Applies to both sequences and single frames with frame ranges
    if not result.frame_range:
        return result

    # Check if frame range starts with dot
    if not result.frame_range.startswith('.'):
        return result

    # Move leading dot to basename
    result.basename += '.'
    result.frame_range = result.frame_range[1:]  # Remove leading dot

    return result
