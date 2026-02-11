grammar fileseq;

// ============================================================================
// Parser Rules
// ============================================================================

input
    : sequence EOF
    | patternOnly EOF
    | singleFrame EOF
    | plainFile EOF
    ;

// Sequence with padding: /path/file.1-100#.exr or /path/file1-100#.exr
// Also handles hidden files: /path/.hidden5.1-10#.7zip
// Basename and extension are optional (allows patterns like /path/1-100#.ext)
// Python-specific: Supports optional subframe patterns:
//   - Dual range: /path/file.1-5#.10-20@@.exr (frameRange with dot prefix + padding)
//   - Composite padding: /path/file.1-5@.#.exr (dot + padding only)
//   Go/C++ ignore the second pair until subframe support is implemented
sequence
    : directory sequenceBasename? frameRange padding (frameRange padding | SPECIAL_CHAR padding)? extension*
    ;

// Pattern-only sequence (padding without frame range): /path/file.@@.ext
// Basename and extension are optional (allows patterns like /path/@@@.ext)
// Python-specific: Supports optional subframe padding: /path/file.#.#.ext
//   Go/C++ ignore the second padding until subframe support is implemented
patternOnly
    : directory patternBasename? padding (SPECIAL_CHAR padding)? extension*
    ;

// Single frame: /path/file.100.exr (extension required after frame number)
// Also handles hidden files: /path/.hidden.100.ext
// Python semantic rule: a dot-number is only treated as a frame if there's an extension after it
// Basename is optional to handle cases like .10000000000.123 where both are DOT_NUM tokens
singleFrame
    : directory singleFrameBasename? frameNum extension+
    ;

// Plain file: /path/file.txt or /path/file or /path/.hidden (no frame pattern)
plainFile
    : directory plainBasename? extension*
    ;

// Directory: optional leading slash + segments ending with slash
directory
    : SLASH? (dirSegment SLASH)*
    ;

// Directory segments can contain anything including frame-range-like patterns
// Includes WS to preserve whitespace in directory names
// Includes OTHER_CHAR for special characters like ! $ % ( ) etc.
dirSegment
    : (WORD | NUM | DASH | SPECIAL_CHAR | FRAME_RANGE | DOT_FRAME_RANGE | DOT_NUM | WS | OTHER_CHAR)+
    ;

// Basename for sequences: can include EXTENSION (for hidden files)
// Also includes FRAME_RANGE tokens for date-like patterns (e.g., "name_2025-05-13_")
// Includes WS and OTHER_CHAR for whitespace and special characters
sequenceBasename
    : (WORD | NUM | DOT_NUM | DASH | SPECIAL_CHAR | EXTENSION | FRAME_RANGE | DOT_FRAME_RANGE | WS | OTHER_CHAR)+
    ;

// Basename for pattern-only: same as sequence
patternBasename
    : (WORD | NUM | DOT_NUM | DASH | SPECIAL_CHAR | EXTENSION | FRAME_RANGE | DOT_FRAME_RANGE | WS | OTHER_CHAR)+
    ;

// Basename for single frames: can include EXTENSION (for hidden files like .hidden.100)
// Also includes FRAME_RANGE for date-like patterns
// Includes WS and OTHER_CHAR for whitespace and special characters
singleFrameBasename
    : (WORD | NUM | DOT_NUM | DASH | SPECIAL_CHAR | EXTENSION | FRAME_RANGE | DOT_FRAME_RANGE | WS | OTHER_CHAR)+
    ;

// Basename for plain files: does NOT include EXTENSION or DOT_NUM
// (so both regular and digit-only extensions can be consumed by extension rule)
// But DOES include FRAME_RANGE tokens (for filenames like "name_2025-05-13.ext")
// Includes WS and OTHER_CHAR for whitespace and special characters
plainBasename
    : (WORD | NUM | DASH | SPECIAL_CHAR | FRAME_RANGE | DOT_FRAME_RANGE | WS | OTHER_CHAR)+
    ;

// Frame range: may or may not have leading dot
// Also includes single frame numbers (for single-frame sequences with padding)
frameRange
    : DOT_FRAME_RANGE
    | FRAME_RANGE
    | DOT_NUM      // Single frame with dot: .100
    | NUM          // Single frame without dot: 100
    ;

// Single frame number with leading dot: .100 or .-10
frameNum
    : DOT_NUM
    ;

// Padding may use mixed characters (e.g. ###@ = 13 chars with HASH4 style)
// Each language's PaddingCharsSize handles per-character width calculation
padding
    : UDIM_ANGLE
    | UDIM_PAREN
    | PRINTF_PAD
    | HOUDINI_PAD
    | (HASH | AT)+
    ;

// Extension can be:
// - EXTENSION tokens (.tar, .gz, .exr)
// - DOT_NUM for digit-only extensions (.123, .10000000000)
// - WORD for non-dot extensions after padding (_exr, _extra)
// - Followed by optional DASH and NUM (for extensions like .tar.gz-1)
extension
    : EXTENSION (DASH NUM)?
    | DOT_NUM
    | WORD
    ;

// ============================================================================
// Lexer Rules - ORDER MATTERS FOR PRIORITY
// ============================================================================

// Padding markers - HIGHEST PRIORITY
// Note: These must come before OTHER_CHAR to match padding first
UDIM_ANGLE: '<UDIM>';
UDIM_PAREN: '%(UDIM)d';
PRINTF_PAD: '%' [0-9]* 'd';
HOUDINI_PAD: '$F' [0-9]*;
HASH: '#';
AT: '@';

// Extension: dot + pattern containing at least one letter
EXTENSION: '.' ([a-zA-Z_] | [0-9]* [a-zA-Z] [a-zA-Z0-9_]*);

// Frame range with leading dot (must have comma, colon, or dash after first number)
// Matches: .1-100, .-10-100, .1,2,3, .1-10x2, .1,2,3,5-10,20-30
// Optional decimal suffix for decimal step values: .1-5x0.25
DOT_FRAME_RANGE: '.' '-'? [0-9]+ [,:-] [0-9xy:,-]* ('.' [0-9]+)?;

// Frame range without leading dot (must have comma, colon, or dash after first number)
// Matches: 1-100, -10-100, 1,2,3, 1-10x2
// Optional decimal suffix for decimal step values: 1-5x0.25
FRAME_RANGE: '-'? [0-9]+ [,:-] [0-9xy:,-]* ('.' [0-9]+)?;

// Frame number with dot: .100 or .-10 (single frame, no range delimiter)
DOT_NUM: '.' '-'? [0-9]+;

// Slash separator
SLASH: '/' | '\\';

// Special characters commonly used in basenames
SPECIAL_CHAR: [:,.];

// Number sequence (for basenames containing numbers)
NUM: [0-9]+;

// Words (letters and underscores, no digits or dashes)
WORD: [a-zA-Z_]+;

// Dash as separate token
DASH: '-';

// Whitespace as token (don't skip - it's part of filenames)
WS: [ \t\r\n]+;

// Other valid filename characters (catch-all for POSIX/Windows filenames)
// Excludes: / \ (path separators), whitespace, and core tokens
// Includes: ! $ % & ' ( ) + ; = [ ] { } ~ and other printable ASCII
// Note: $ and % may conflict with padding tokens (HOUDINI_PAD, PRINTF_PAD) in edge cases
// This is acceptable - such patterns are rare in VFX workflows
OTHER_CHAR: ~[/\\\r\n\t .,:a-zA-Z0-9_#@<>-]+;
