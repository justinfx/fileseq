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
    :param start: int
    :param stop: int
    :param step: int (sign will be ignored)
    :return: generator
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
    :return: generator
    """
    _add = seen.add
    # return a generator of the unique items and the set of the seen items
    # the seen set will mutate when the generator is iterated over
    return (i for i in chain(*iterables) if i not in seen and not _add(i))

def pad(number, width=0):
    """
    Return the zero-padded string of a given number.
    :param number: the number to pad (int)
    :param width: width for zero padding (int)
    :return: str
    """
    return str(number).zfill(width)
