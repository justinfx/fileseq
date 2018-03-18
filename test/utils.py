import os
import sys

TEST_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(TEST_DIR, "../src")
sys.path.insert(0, SRC_DIR)
os.chdir(TEST_DIR)


def _getCommonPathSep(path):
    """
    Find the most common path seperator character used
    in a given path. Because windows supports both forward
    and backward sep characters, find the most consistently
    used.
    Defaults to ``os.sep``

    :type path: str
    :param path: A path to check for the most common sep
    :rtype: str
    """
    sep = os.sep
    count = 0
    for nextSep in ('/', '\\'):
        if path.count(nextSep) > count:
            sep = nextSep
    return sep

import fileseq.utils
fileseq.utils._getPathSep = _getCommonPathSep
