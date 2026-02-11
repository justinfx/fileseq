"""
Main parser entry point using ANTLR4.

Based on Go implementation at gofileseq/fileseq.go
"""
from typing import Optional

from antlr4 import InputStream, CommonTokenStream, ParseTreeVisitor
from antlr4.error.ErrorListener import ErrorListener
from antlr4.atn.PredictionMode import PredictionMode

from .fileseqLexer import fileseqLexer
from .fileseqParser import fileseqParser
from .fileseq_visitor_impl import FileSeqVisitorImpl
from .parse_postprocess import post_process
from .parse_result import ParseResult


class FileSeqErrorListener(ErrorListener):
    """Custom error listener for ANTLR parsing errors."""

    def __init__(self):
        super().__init__()
        self.errors = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        """Record syntax errors."""
        self.errors.append({
            'line': line,
            'column': column,
            'message': msg,
            'symbol': offendingSymbol
        })


def parse_file_sequence(path: str) -> Optional[ParseResult]:
    """
    Parse a file sequence path using ANTLR4 grammar.

    Uses two-tier prediction mode strategy for performance:
    1. Try SLL mode first (fast, handles most cases)
    2. Fall back to LL mode if SLL fails (slower, more thorough)

    Args:
        path: File path to parse (e.g., "/path/file.1-100#.exr")

    Returns:
        ParseResult if successful, None if parse failed

    Raises:
        ValueError: If parsing fails with error details

    Example:
        >>> result = parse_file_sequence("/path/file.1-100#.exr")
        >>> result.is_sequence
        True
        >>> result.basename
        'file.'
        >>> result.frame_range
        '1-100'
    """
    # Create input stream
    input_stream = InputStream(path)

    # Create lexer with error handling
    lexer = fileseqLexer(input_stream)
    lexer_error_listener = FileSeqErrorListener()
    lexer.removeErrorListeners()
    lexer.addErrorListener(lexer_error_listener)

    # Create token stream
    token_stream = CommonTokenStream(lexer)

    # Create parser with error handling
    parser = fileseqParser(token_stream)
    parser_error_listener = FileSeqErrorListener()
    parser.removeErrorListeners()
    parser.addErrorListener(parser_error_listener)

    # Try SLL prediction mode first (30x faster for unambiguous grammars)
    parser._interp.predictionMode = PredictionMode.SLL

    try:
        tree = parser.input_()

        # Check if SLL mode had errors
        if lexer_error_listener.errors or parser_error_listener.errors:
            # Retry with LL mode for better error handling
            input_stream.seek(0)
            lexer = fileseqLexer(input_stream)
            lexer.removeErrorListeners()

            token_stream = CommonTokenStream(lexer)
            parser = fileseqParser(token_stream)
            parser.removeErrorListeners()
            parser_error_listener = FileSeqErrorListener()
            parser.addErrorListener(parser_error_listener)

            # Use LL mode (slower but more thorough)
            parser._interp.predictionMode = PredictionMode.LL
            tree = parser.input_()

            # Check for errors again
            if parser_error_listener.errors:
                error_msgs = [e['message'] for e in parser_error_listener.errors]
                raise ValueError(
                    f"Failed to parse '{path}': " + "; ".join(error_msgs)
                )

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to parse '{path}': {e}")

    # Visit parse tree to extract components
    visitor = FileSeqVisitorImpl()
    result = visitor.visit(tree)

    if result is None:
        raise ValueError(f"Failed to extract components from '{path}'")

    # Apply post-processing for special cases
    result = post_process(result)

    return result
