"""ANTLR4-generated parser for fileseq grammar.

This package contains the generated parser from the ANTLR4 grammar file.

To regenerate the parser after modifying the grammar:
    java -jar tools/antlr-4.13.1-complete.jar \\
        -Dlanguage=Python3 \\
        -visitor \\
        -o src/fileseq/parser \\
        src/fileseq/grammar/fileseq.g4

Or using hatch:
    hatch run generate-parser
"""

try:
    from .fileseqLexer import fileseqLexer
    from .fileseqParser import fileseqParser
    from .fileseqVisitor import fileseqVisitor
    __all__ = ['fileseqLexer', 'fileseqParser', 'fileseqVisitor']
except ImportError:
    # Parser files not yet generated
    __all__ = []
