"""Custom visitor for fileseq ANTLR4 grammar.

This module implements the visitor pattern to extract file sequence components
from the ANTLR parse tree.

Based on Go implementation at gofileseq/internal/parser/parse.go
"""
from typing import Any, List, Optional

from fileseq._vendor.antlr4 import ParseTreeVisitor  # type: ignore[import-untyped]

from .parse_result import ParseResult


class FileSeqVisitorImpl(ParseTreeVisitor):
    """
    Visitor that extracts file sequence components from ANTLR parse tree.

    Based on Go implementation at gofileseq/internal/parser/parse.go
    """

    # ========================================================================
    # Main Entry Points (one of these will be called based on parse tree)
    # ========================================================================

    def visitInput(self, ctx: Any) -> Optional[ParseResult]:
        """Visit input rule - delegates to specific rule visitors."""
        # The input rule matches one of: sequence, patternOnly, singleFrame, plainFile
        # Delegate to the appropriate child
        if ctx.getChildCount() > 0:
            return self.visit(ctx.getChild(0))
        return None

    def visitSequence(self, ctx: Any) -> ParseResult:
        """
        Visit sequence rule: /path/file.1-100#.exr

        Grammar (with optional Python subframe support):
            directory sequenceBasename? frameRange padding (frameRange padding | SPECIAL_CHAR padding)? extension*

        Subframe patterns:
            - Dual range: /path/file.1-5#.10-20@@.exr (main frames + subframes)
            - Composite padding: /path/file.1-5@.#.exr (subframes + frame padding)
        """
        result = ParseResult(is_sequence=True)
        result.directory = ctx.directory().getText()
        if bn := ctx.basename():
            result.basename = bn.getText()

        # Extract frame ranges and paddings (can have 1 or 2 for Python subframes)
        # Note: leading dot in frame range text will be moved to basename in post-processing
        frame_ranges = self._collect_indexed(ctx, "frameRange")
        paddings = self._collect_indexed(ctx, "padding")

        if len(frame_ranges) == 2:
            # Dual range pattern: main frames + subframes
            # e.g., /path/file.1-5#.10-20@@.exr
            result.frame_range = frame_ranges[0].getText()
            result.padding = paddings[0].getText()
            if len(paddings) == 2:
                result.subframe_range = frame_ranges[1].getText()
                result.padding = f"{result.padding}.{paddings[1].getText()}"

        elif len(frame_ranges) == 1 and len(paddings) == 2:
            # Composite padding pattern: subframe range + frame padding
            # e.g., /path/file.1-5@.#.exr
            result.frame_range = frame_ranges[0].getText()
            result.padding = f"{paddings[0].getText()}.{paddings[1].getText()}"

        elif len(frame_ranges) == 1 and len(paddings) == 1:
            # Standard pattern: single frame range + padding
            result.frame_range = frame_ranges[0].getText()
            result.padding = paddings[0].getText()

        if exts := ctx.extension():
            result.extension = ''.join(ext.getText() for ext in exts)

        return result

    def visitPatternOnly(self, ctx: Any) -> ParseResult:
        """
        Visit patternOnly rule: /path/file.@@.ext

        Grammar (with optional Python subframe support):
            directory patternBasename? padding (SPECIAL_CHAR padding)? extension*
        """
        result = ParseResult(is_sequence=True)
        result.directory = ctx.directory().getText()
        if bn := ctx.basename():
            result.basename = bn.getText()

        paddings = self._collect_indexed(ctx, "padding")

        if len(paddings) == 2:
            result.padding = f"{paddings[0].getText()}.{paddings[1].getText()}"

        elif len(paddings) == 1:
            result.padding = paddings[0].getText()

        if exts := ctx.extension():
            result.extension = ''.join(ext.getText() for ext in exts)

        # No frame_range for pattern-only
        return result

    def visitSingleFrame(self, ctx: Any) -> ParseResult:
        """
        Visit singleFrame rule: /path/file.100.exr

        Grammar: directory singleFrameBasename? frameNum extension+

        Note: Extension MUST follow frame number (Python canonical behavior)
        """
        result = ParseResult(is_single_frame=True)
        result.directory = ctx.directory().getText()
        if bn := ctx.basename():
            result.basename = bn.getText()

        # Extract frame number from DOT_NUM or NUM token
        # Keep the leading dot if present - post-processing will move it to basename
        if frame_num := ctx.frameNum():
            if dot_num := frame_num.DOT_NUM():
                result.frame_range = dot_num.getText()
            elif num := frame_num.NUM():
                result.frame_range = num.getText()

        if exts := ctx.extension():
            result.extension = ''.join(ext.getText() for ext in exts)

        return result

    def visitPlainFile(self, ctx: Any) -> ParseResult:
        """
        Visit plainFile rule: /path/file.txt

        Grammar: directory plainBasename? extension*
        """
        result = ParseResult(is_plain_file=True)
        result.directory = ctx.directory().getText()

        if bn := ctx.plainBasename():
            result.basename = bn.getText()

        if exts := ctx.extension():
            result.extension = ''.join(ext.getText() for ext in exts)

        return result

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _collect_indexed(self, ctx: Any, method: str) -> List[Any]:
        """Collect up to 2 indexed rule contexts, handling both indexed and single forms."""
        results = []
        try:
            for i in range(2):
                item = getattr(ctx, method)(i)
                if item:
                    results.append(item)

        except (AttributeError, TypeError):
            item = getattr(ctx, method)()
            if item:
                results.append(item)

        return results
