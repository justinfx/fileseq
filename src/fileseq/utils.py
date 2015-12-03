#! /usr/bin/env python
"""
utils - General tools of use to fileseq operations.
"""

from itertools import chain

def xfrange(start, stop, step=1):
    """
    Returns a generator that yields the frames from start to stop, inclusive.
    In other words it adds or subtracts a frame, as necessary, to return the
    stop value as well, if the stepped range would touch that value.

    :type start: int
    :type stop: int
    :type step: int
    :param step: Note that the sign will be ignored
    :rtype: generator
    """
    if start <= stop:
        stop, step = stop + 1, abs(step)
    else:
        stop, step = stop - 1, -abs(step)
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
