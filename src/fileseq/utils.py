#! /usr/bin/env python
"""
utils - General tools of use to fileseq operations.
"""
from __future__ import absolute_import, division

from builtins import bytes
from builtins import next
from builtins import range
from builtins import object
import future.utils as futils

import decimal
from itertools import chain, count, islice
import os
import sys

from fileseq import exceptions


FILESYSTEM_ENCODING = sys.getfilesystemencoding() or 'utf-8'


def quantize(number, decimal_places, rounding=decimal.ROUND_HALF_EVEN):
    """
    Round a decimal value to given number of decimal places

    Args:
        number (decimal.Decimal): Decimal number to round
        decimal_places (int): Number of decimal places in return value
        rounding (str): decimal.Decimal rounding mode. See rounding argument of
            https://docs.python.org/2/library/decimal.html#decimal.Context

    Returns:
        decimal.Decimal:
    """
    quantize_exponent = decimal.Decimal(1).scaleb(-decimal_places)
    return number.quantize(quantize_exponent, rounding=rounding)


def lenRange(start, stop, step=1):
    """
    Get the length of values for a given range, exclusive of the stop

    Args:
        start (int):
        stop (int):
        step (int):
    """
    if not step:
        raise ValueError('step argument must not be zero')

    if step > 0:
        result = (stop - start + step - 1) // step
    else:
        result = (stop - start + step + 1) // step

    return max(0, result)


class xrange2(object):
    """
    An itertools-based replacement for xrange which does
    not exhibit the OverflowError issue on some platforms,
    when a value exceeds a C long size.

    Provides the features of an islice, with the added support
    for checking the length of the range.
    """

    __slots__ = ['_len', '_islice', '_start', '_stop', '_step']

    def __init__(self, start, stop=None, step=1):
        if stop is None:
            start, stop = 0, start

        self._len = lenRange(start, stop, step)
        self._islice = islice(count(start, step), self._len)
        self._start = start
        self._stop = stop
        self._step = step

    def __repr__(self):
        if self._step == 1:
            return 'range({}, {})'.format(self._start, self._stop)
        else:
            return 'range({}, {}, {})'.format(self._start, self._stop, self._step)

    def __len__(self):
        return self._len

    def __next__(self):
        return next(self._islice)

    def __iter__(self):
        return self._islice.__iter__()

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def step(self):
        return self._step


# Issue #44
# On Windows platform, it is possible for xrange to get an
# OverflowError if a value passed to xrange exceeds the size of a C long.
# Switch to an alternate implementation.
if os.name == 'nt':
    xrange = range = xrange2
else:
    xrange = range


class _islice(object):

    def __init__(self, gen, start, stop, step=1):
        self._gen = gen
        self._start = start
        self._stop = stop
        self._step = step

    def __len__(self):
        return lenRange(self._start, self._stop, self._step)

    def __next__(self):
        return next(self._gen)

    def __iter__(self):
        return self._gen.__iter__()

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def step(self):
        return self._step


class _xfrange(_islice):

    def __len__(self):
        stop = self._stop + (1 if self._start <= self._stop else -1)
        return lenRange(self._start, stop, self._step)


def xfrange(start, stop, step=1, maxSize=-1):
    """
    Returns a generator that yields the frames from start to stop, inclusive.
    In other words it adds or subtracts a frame, as necessary, to return the
    stop value as well, if the stepped range would touch that value.

    Args:
        start (int):
        stop (int):
        step (int): Note that the sign will be ignored
        maxSize (int):

    Returns:
        generator:

    Raises:
        :class:`fileseq.exceptions.MaxSizeException`: if size is exceeded
    """
    if not step:
        raise ValueError('xfrange() step argument must not be zero')

    start, stop, step = normalizeFrames([start, stop, step])

    if start <= stop:
        step = abs(step)
    else:
        step = -abs(step)

    if isinstance(start, futils.integer_types):
        size = (stop - start) // step + 1
    else:
        size = int((stop - start) / step) + 1

    if maxSize >= 0 and size > maxSize:
        raise exceptions.MaxSizeException(
            "Size %d > %s (MAX_FRAME_SIZE)" % (size, maxSize))

    # because an xrange is an odd object all its own, we wrap it in a
    # generator expression to get a proper Generator
    if isinstance(start, futils.integer_types):
        offset = step // abs(step)
        gen = (f for f in range(start, stop + offset, step))
    else:
        gen = (start + i * step for i in range(size))

    return _xfrange(gen, start, stop, step)


def batchFrames(start, stop, batch_size):
    """
    Returns a generator that yields batches of frames from start to stop, inclusive.
    Each batch value is a ``range`` generator object, also providing start, stop, and
    step properties.
    The last batch frame length may be smaller if the batches cannot be divided evenly.

    start value is allowed to be greater than stop value, to generate decreasing frame
    values.

    Args:
        start (int): start frame value
        stop (int): stop frame value
        batch_size (int): max size of each batch

    Yields:
        range(sub_start, sub_stop)
    """
    if batch_size <= 0:
        return

    for i in xfrange(start, stop, batch_size):
        if start <= stop:
            sub_stop = min(i - 1 + batch_size, stop)
        else:
            sub_stop = max(i + 1 - batch_size, stop)
        yield xfrange(i, sub_stop)


def batchIterable(it, batch_size):
    """
    Returns a generator that yields batches of items returned by the given iterable.
    The last batch frame length may be smaller if the batches cannot be divided evenly.

    Args:
        it (iterable): An iterable from which to yield batches of values
        batch_size (int): max size of each batch

    Yields:
        iterable: a subset of batched items
    """
    if batch_size <= 0:
        return

    # Try to get the length. If it is a generator with no
    # known length, then we have to use a less efficient
    # method that builds results by exhausting the generator
    try:
        length = len(it)
    except TypeError:
        for b in _batchGenerator(it, batch_size):
            yield b
        return

    # We can use the known length to yield slices
    for start in xrange(0, length, batch_size):
        stop = start + batch_size
        gen = islice(it, start, stop)
        yield _islice(gen, start, stop)


def _batchGenerator(gen, batch_size):
    """
    A batching generator function that handles a generator
    type, where the length isn't known.

    Args:
        gen: generator object
        batch_size (int): max size of each batch

    Yields:
        iterable: a subset of batched items
    """
    batch = []
    for item in gen:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def normalizeFrame(frame):
    """
    Convert a frame number to the most appropriate type - the most compact type
    that doesn't affect precision, for example numbers that convert exactly
    to integer values will be converted to int

    Args:
        frame (int, float, decimal.Decimal, str): frame number to normalize

    Returns:
        frame (int, float, or decimal.Decimal):
    """
    if frame is None:
        return None
    elif isinstance(frame, futils.integer_types):
        return frame
    elif isinstance(frame, float):
        frame_int = int(frame)
        if frame == frame_int:
            return frame_int
        return frame
    elif isinstance(frame, decimal.Decimal):
        frame_int = int(frame)
        if frame == frame_int:
            return frame_int
        return frame.normalize()
    else:
        try:
            return int(frame)
        except ValueError:
            try:
                frame = decimal.Decimal(frame)
            except decimal.DecimalException:
                return frame
            else:
                return normalizeFrame(frame)


def normalizeFrames(frames):
    """
    Convert a sequence of frame numbers to the most appropriate type for the
    overall sequence, where all members of the result are of the same type.

    Args:
        frames (iterable of int, float, decimal.Decimal, or str):
            frame numbers to normalize

    Returns:
        frames (iterable of int, float, or decimal.Decimal):
    """

    # Normalise all frame values and find their type
    frames = [normalizeFrame(frame) for frame in frames]
    frame_types = set(type(frame) for frame in frames)

    # Determine best overall type for frames
    if float in frame_types:
        FrameType = float
    elif decimal.Decimal in frame_types:
        FrameType = decimal.Decimal
    else:
        FrameType = int

    if len(frame_types) == 1:
        return frames

    # Convert all frames to chosen type
    frames = [FrameType(frame) for frame in frames]

    # Ensure all decimal frames have same exponent
    if FrameType is decimal.Decimal:
        maximum_decimal_places = max(
            -frame.as_tuple().exponent for frame in frames
        )
        frames = [quantize(frame, maximum_decimal_places) for frame in frames]

    return frames


def unique(seen, *iterables):
    """
    Get the unique items in iterables while preserving order.  Note that this
    mutates the seen set provided only when the returned generator is used.

    Args:
        seen (set): either an empty set, or the set of things already seen
        *iterables: one or more iterable lists to chain together

    Returns:
        generator:
    """
    _add = seen.add
    # return a generator of the unique items and the set of the seen items
    # the seen set will mutate when the generator is iterated over
    return (i for i in chain(*iterables) if i not in seen and not _add(i))


def pad(number, width=0, decimal_places=None):
    """
    Return the zero-padded string of a given number.

    Args:
        number (int, float, or decimal.Decimal): the number to pad
        width (int): width for zero padding the integral component
        decimal_places (int): number of decimal places to use in frame range

    Returns:
        str:
    """

    # Make the common case fast. Truncate to integer value as USD does.
    # https://graphics.pixar.com/usd/docs/api/_usd__page__value_clips.html
    # See _DeriveClipTimeString for formating of templateAssetPath
    # https://github.com/PixarAnimationStudios/USD/blob/release/pxr/usd/usd/clipSetDefinition.cpp
    if decimal_places == 0:
        return futils.native_str(number).partition(".")[0].zfill(width)

    # USD ultimately uses vsnprintf to format floats for templateAssetPath:
    # _DeriveClipTimeString -> TfStringPrintf -> ArchVStringPrintf -> ArchVsnprintf -> vsnprintf
    # Since glibc 2.17 the printf family of functions rounds floats using the
    # current IEEE rounding mode, by default bankers' rounding (FE_TONEAREST).
    # See https://sourceware.org/bugzilla/show_bug.cgi?id=5044 and man(3) fegetround
    # Also https://www.exploringbinary.com/inconsistent-rounding-of-printed-floating-point-numbers/
    if decimal_places is not None:
        if not isinstance(number, decimal.Decimal):
            number = decimal.Decimal(number)
        number = quantize(number, decimal_places, decimal.ROUND_HALF_EVEN)

    number = futils.native_str(number)

    parts = number.split(".", 1)
    parts[0] = parts[0].zfill(width)
    return ".".join(parts)


def _getPathSep(path):
    """
    Abstracts returning the appropriate path separator
    for the given path string.

    This implementation always returns ``os.sep``

    Abstracted to make test mocking easier.

    Args:
        path (str): A path to check for the most common sep

    Returns:
        str:
    """
    return os.sep


_STR_TYPES = frozenset((futils.text_type, futils.binary_type))


def asString(obj):
    """
    Ensure an object is either explicitly str or unicode
    and not some derived type that can change semantics.

    If the object is unicode, return unicode.
    Otherwise return the string conversion of the object.

    Args:
        obj: Object to return as str or unicode

    Returns:
        str or unicode:
    """
    typ = type(obj)
    # explicit type check as faster path
    if typ in _STR_TYPES:
        if not futils.PY2 and typ is futils.binary_type:
            obj = os.fsdecode(obj)
        return obj
    # derived type check
    elif isinstance(obj, bytes):
        if futils.PY2:
            obj = bytes(obj)
        else:
            obj = obj.decode(FILESYSTEM_ENCODING)
    else:
        obj = futils.text_type(obj)
    return futils.native(obj)
