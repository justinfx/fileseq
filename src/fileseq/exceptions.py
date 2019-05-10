#! /usr/bin/env python
"""
exceptions - Exception subclasses relevant to fileseq operations.
"""


class FileSeqException(ValueError):
    """
    Thrown for general exceptions handled by FileSeq.
    """
    pass


class MaxSizeException(ValueError):
    """
    Thrown when a range exceeds allowable size.
    """
    pass


class ParseException(FileSeqException):
    """
    Thrown after a frame range or file sequence parse error.
    """
    pass
