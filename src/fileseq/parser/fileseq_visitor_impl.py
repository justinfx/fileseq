"""Custom visitor for fileseq ANTLR4 grammar.

This module implements the visitor pattern to extract file sequence components
from the ANTLR parse tree.

Based on Go implementation at gofileseq/internal/parser/parse.go
"""
from typing import List, Optional

from antlr4 import ParseTreeVisitor

from .parse_result import ParseResult


class FileSeqVisitorImpl(ParseTreeVisitor):
    """
    Visitor that extracts file sequence components from ANTLR parse tree.

    Based on Go implementation at gofileseq/internal/parser/parse.go
    """

    def __init__(self):
        super().__init__()
        # Don't initialize result here - let visitor methods create it with proper flags

    # ========================================================================
    # Main Entry Points (one of these will be called based on parse tree)
    # ========================================================================

    def visitInput(self, ctx):
        """Visit input rule - delegates to specific rule visitors."""
        # The input rule matches one of: sequence, patternOnly, singleFrame, plainFile
        # Delegate to the appropriate child
        if ctx.getChildCount() > 0:
            return self.visit(ctx.getChild(0))
        return None

    def visitSequence(self, ctx):
        """
        Visit sequence rule: /path/file.1-100#.exr

        Grammar (with optional Python subframe support):
            directory sequenceBasename? frameRange padding (frameRange padding | SPECIAL_CHAR padding)? extension*

        Subframe patterns:
            - Dual range: /path/file.1-5#.10-20@@.exr (main frames + subframes)
            - Composite padding: /path/file.1-5@.#.exr (subframes + frame padding)
        """
        result = ParseResult(is_sequence=True)
        result.directory = self._visit_directory(ctx.directory())
        if ctx.sequenceBasename():
            result.basename = self._visit_basename(ctx.sequenceBasename())

        # Extract frame ranges (can have 1 or 2 for Python subframes)
        # Try to get indexed frameRange contexts (grammar allows multiple)
        frame_ranges = []
        try:
            fr0 = ctx.frameRange(0)
            if fr0:
                frame_ranges.append(fr0)
            fr1 = ctx.frameRange(1)
            if fr1:
                frame_ranges.append(fr1)
        except (AttributeError, TypeError):
            # Single frameRange (not indexed)
            if ctx.frameRange():
                frame_ranges.append(ctx.frameRange())

        # Extract paddings (can have 1 or 2 for Python subframes)
        paddings = []
        try:
            p0 = ctx.padding(0)
            if p0:
                paddings.append(p0)
            p1 = ctx.padding(1)
            if p1:
                paddings.append(p1)
        except (AttributeError, TypeError):
            # Single padding (not indexed)
            if ctx.padding():
                paddings.append(ctx.padding())

        # Handle subframe patterns
        if len(frame_ranges) == 2:
            # Dual range pattern: main frames + subframes
            # e.g., /path/file.1-5#.10-20@@.exr
            result.frame_range = self._visit_frame_range(frame_ranges[0])  # Main frames
            result.padding = self._visit_padding(paddings[0])  # Main padding
            if len(paddings) == 2:
                # Store subframe range and padding separately
                result.subframe_range = self._visit_frame_range(frame_ranges[1])
                subframe_padding = self._visit_padding(paddings[1])
                # Combine paddings: frame_padding.subframe_padding
                result.padding = f"{result.padding}.{subframe_padding}"
        elif len(frame_ranges) == 1 and len(paddings) == 2:
            # Composite padding pattern: subframe range + frame padding (no main frame range with padding)
            # e.g., /path/file.1-5@.#.exr
            result.frame_range = self._visit_frame_range(frame_ranges[0])  # Subframe range
            result.padding = f"{self._visit_padding(paddings[0])}.{self._visit_padding(paddings[1])}"
        elif len(frame_ranges) == 1 and len(paddings) == 1:
            # Standard pattern: single frame range + padding
            result.frame_range = self._visit_frame_range(frame_ranges[0])
            result.padding = self._visit_padding(paddings[0])

        if ctx.extension():
            result.extension = self._visit_extensions(ctx.extension())
        return result

    def visitPatternOnly(self, ctx):
        """
        Visit patternOnly rule: /path/file.@@.ext

        Grammar (with optional Python subframe support):
            directory patternBasename? padding (SPECIAL_CHAR padding)? extension*
        """
        result = ParseResult(is_sequence=True)
        result.directory = self._visit_directory(ctx.directory())
        if ctx.patternBasename():
            result.basename = self._visit_basename(ctx.patternBasename())

        # Extract paddings (can have 1 or 2 for Python subframes)
        paddings = []
        try:
            p0 = ctx.padding(0)
            if p0:
                paddings.append(p0)
            p1 = ctx.padding(1)
            if p1:
                paddings.append(p1)
        except (AttributeError, TypeError):
            # Single padding (not indexed)
            if ctx.padding():
                paddings.append(ctx.padding())

        # Handle subframe padding: #.# pattern
        if len(paddings) == 2:
            result.padding = f"{self._visit_padding(paddings[0])}.{self._visit_padding(paddings[1])}"
        elif len(paddings) == 1:
            result.padding = self._visit_padding(paddings[0])

        if ctx.extension():
            result.extension = self._visit_extensions(ctx.extension())
        # No frame_range for pattern-only
        return result

    def visitSingleFrame(self, ctx):
        """
        Visit singleFrame rule: /path/file.100.exr

        Grammar: directory singleFrameBasename? frameNum extension+

        Note: Extension MUST follow frame number (Python canonical behavior)
        """
        result = ParseResult(is_single_frame=True)
        result.directory = self._visit_directory(ctx.directory())
        if ctx.singleFrameBasename():
            result.basename = self._visit_basename(ctx.singleFrameBasename())

        # Extract frame number from DOT_NUM or NUM token
        # Keep the leading dot if present - post-processing will move it to basename
        if ctx.frameNum():
            if ctx.frameNum().DOT_NUM():
                frame_text = ctx.frameNum().DOT_NUM().getText()
                result.frame_range = frame_text  # Keep dot: ".100"
            elif ctx.frameNum().NUM():
                frame_text = ctx.frameNum().NUM().getText()
                result.frame_range = frame_text  # No dot: "100"

        if ctx.extension():
            result.extension = self._visit_extensions(ctx.extension())
        return result

    def visitPlainFile(self, ctx):
        """
        Visit plainFile rule: /path/file.txt

        Grammar: directory plainBasename? extension*
        """
        result = ParseResult(is_plain_file=True)
        result.directory = self._visit_directory(ctx.directory())
        if ctx.plainBasename():
            result.basename = self._visit_basename(ctx.plainBasename())
        if ctx.extension():
            result.extension = self._visit_extensions(ctx.extension())
        return result

    # ========================================================================
    # Helper Methods - Extract Text from Contexts
    # ========================================================================

    def _visit_directory(self, ctx) -> str:
        """
        Extract directory path from directory context.

        Preserves path separators (/ or \\) from input.
        """
        if not ctx:
            return ""
        return ctx.getText()

    def _visit_basename(self, ctx) -> str:
        """Extract basename from basename context (various rules)."""
        if not ctx:
            return ""
        return ctx.getText()

    def _visit_frame_range(self, ctx) -> str:
        """
        Extract frame range from frameRange context.

        May include leading dot which needs to be handled in post-processing.
        Examples: "1-100", ".1-100", "1,2,3", ".1-100x2"
        """
        if not ctx:
            return ""

        text = ctx.getText()
        # Note: Leading dot will be moved to basename in post-processing
        return text

    def _visit_padding(self, ctx) -> str:
        """
        Extract padding string from padding context.

        Examples: "#", "@@@@", "%04d", "$F4", "<UDIM>"
        """
        if not ctx:
            return ""
        return ctx.getText()

    def _visit_extensions(self, ctx: List) -> str:
        """
        Extract concatenated extensions from list of extension contexts.

        Handles multi-part extensions: .tar.gz, .bgeo.sc
        """
        if not ctx:
            return ""

        # Concatenate all extension parts
        extensions = []
        for ext_ctx in ctx:
            extensions.append(ext_ctx.getText())

        return ''.join(extensions)
