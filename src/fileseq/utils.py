#! /usr/bin/env python
"""
utils - General tools of use to fileseq operations.
"""

import os
from itertools import chain, count, islice

from fileseq import exceptions 


def lenRange(start, stop, step=1):
    """
    Get the length of values for a given range
    """
    return (stop - start + step - 1 + 2 * (step < 0)) // step


class xrange2(object):
    """
    An itertools-based replacement for xrange which does
    not exhibit the OverflowError issue on some platforms, 
    when a value exceeds a C long size.
    
    Provides the features of an islice, with the added support
    for checking the length of the range.
    """
    
    __slots__ = ['_len', '_islice']
    
    def __init__(self, start, stop=None, step=1):
        if stop is None:
            start, stop = 0, start

        self._len = lenRange(start, stop, step)
        self._islice = islice(count(start, step), self._len)
    
    def __len__(self):
        return self._len 
    
    def next(self):
        return self._islice.next()
    
    def __iter__(self):
        return self._islice.__iter__()
    

# Issue #44
# On Windows platform, it is possible for xrange to get an
# OverflowError if a value passed to xrange exceeds the size of a C long. 
# Switch to an alternate implementation.
if os.name == 'nt':
    xrange = xrange2
else:
    xrange = xrange


def xfrange(start, stop, step=1, maxSize=-1):
    """
    Returns a generator that yields the frames from start to stop, inclusive.
    In other words it adds or subtracts a frame, as necessary, to return the
    stop value as well, if the stepped range would touch that value.

    :type start: int
    :type stop: int
    :type step: int
    :param step: Note that the sign will be ignored
    :type maxSize: int
    :param maxSize: If >= raise a :class:`fileseq.exceptions.MaxSizeException` 
                    if size is exceeded
    :rtype: generator
    """
    if start <= stop:
        stop, step = stop + 1, abs(step)
    else:
        stop, step = stop - 1, -abs(step)
        
    if maxSize >= 0:
        size = lenRange(start, stop, step)
        if size > maxSize:
            raise exceptions.MaxSizeException(
                "Size %d > %s (MAX_FRAME_SIZE)" % (size, maxSize))
        
    # because an xrange is an odd object all its own, we wrap it in a
    # generator expression to get a proper Generator
    return (f for f in xrange(start, stop, step))

def unique(seen, *iterables):
    """
    Get the unique items in iterables while preserving order.  Note that this
    mutates the seen set provided only when the returned generator is used.

    :param seen: either an empty set, or the set of things already seen
    :param iterables: one or more iterable lists to chain together
    :rtype: generator
    """
    _add = seen.add
    # return a generator of the unique items and the set of the seen items
    # the seen set will mutate when the generator is iterated over
    return (i for i in chain(*iterables) if i not in seen and not _add(i))

def pad(number, width=0):
    """
    Return the zero-padded string of a given number.

    :type number: int
    :param number: the number to pad
    :type width: int
    :param width: width for zero padding
    :rtype: str
    """
    return str(number).zfill(width)

def _getPathSep(path):
    """
    Abstracts returning the appropriate path separator 
    for the given path string. 

    This implementation always returns ``os.sep``

    Abstracted to make test mocking easier.

    :type path: str
    :param path: A path to check for the most common sep
    :rtype: str
    """
    return os.sep

_STR_TYPES = frozenset((unicode, str, bytes))

def asString(obj):
    """
    Ensure an object is either explicitly str or unicode
    and not some derived type that can change semantics.

    If the object is unicode, return unicode.
    Otherwise return the string conversion of the object.

    :type obj: Object to return as str or unicode
    :rtype: str or unicode
    """
    if type(obj) in _STR_TYPES:
        return obj
    return str(obj)