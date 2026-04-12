"""
frameset - A set-like object representing a frame range for fileseq.
"""
from __future__ import annotations

import dataclasses
import decimal
import numbers
import typing
import warnings
from collections.abc import Set, Sized, Iterable
from typing import Union, overload

from . import constants  # constants.MAX_FRAME_SIZE updated during tests
from .constants import PAD_MAP, FRANGE_RE, PAD_RE
from .exceptions import MaxSizeException, ParseException
from .utils import (asString, xfrange, unique, pad, quantize,
                    normalizeFrame, normalizeFrames, batchIterable, _islice)

# Type alias for frame values
FrameValue = Union[int, float, decimal.Decimal]

# Internal type alias for a (start, end) interval pair used in coverage/gap calculations
_Interval = tuple[decimal.Decimal, decimal.Decimal]

# Type alias for FrameSet constructor input
FrameSetInput = Union[
    str,                                    # Frame range string like "1-10", "1-100x5"
    'FrameSet',                            # Another FrameSet (copy constructor)
    typing.Iterable[FrameValue],           # General iterable of frame numbers
    FrameValue,                            # Individual frame number
]

if typing.TYPE_CHECKING:
    BaseFrameSet = Set[FrameValue]
else:
    BaseFrameSet = Set


@dataclasses.dataclass(frozen=True)
class Range:
    """Compact representation of a frame range with start, end, and step"""
    __slots__ = ('start', 'end', 'step')
    start: decimal.Decimal
    end: decimal.Decimal
    step: decimal.Decimal

    def __contains__(self, frame: FrameValue) -> bool:
        """Check if frame is in this range"""
        frame_dec = decimal.Decimal(str(frame))
        if self.step > 0:
            if not (self.start <= frame_dec <= self.end):
                return False
        else:
            if not (self.end <= frame_dec <= self.start):
                return False
        # check if frame aligns with step
        offset = abs(frame_dec - self.start)
        return offset % abs(self.step) == 0

    def __iter__(self) -> typing.Iterator[FrameValue]:
        """Iterate through frames in this range"""
        step = abs(self.step)
        has_subframes = (self.start % 1 != 0 or self.end % 1 != 0 or step % 1 != 0)
        if not has_subframes:
            # use native int arithmetic for integer ranges
            start, end, istep = int(self.start), int(self.end), int(step)
            if start <= end:
                yield from range(start, end + 1, int(istep))
            else:
                yield from range(start, end - 1, int(-istep))
            return
        current = self.start
        if self.start <= self.end:
            while current <= self.end:
                yield current
                current += step
        else:
            while current >= self.end:
                yield current
                current -= step

    def __len__(self) -> int:
        """Return number of frames in this range"""
        if self.step == 0:
            return 0
        return int(abs(self.end - self.start) / abs(self.step)) + 1


_D0 = decimal.Decimal(0)
_D1 = decimal.Decimal(1)


def _all_ranges_contiguous(ranges: list[Range]) -> bool:
    """Return True if every range has a step of 1 or -1."""
    for r in ranges:
        if r.step != _D1 and r.step != -_D1:
            return False
    return True


def _merged_coverage(ranges: list[Range]) -> list[_Interval]:
    """Return sorted, merged bounding intervals from a list of ranges.

    Each entry is ``(lo, hi)`` where ``lo <= hi``. Adjacent intervals
    (e.g. [1,5] and [6,10]) are merged into one.
    """
    if not ranges:
        return []

    # collect one (lo, hi) pair per range block
    intervals = [(min(r.start, r.end), max(r.start, r.end)) for r in ranges]
    intervals.sort()

    merged: list[_Interval] = [intervals[0]]
    for lo, hi in intervals[1:]:
        prev_lo, prev_hi = merged[-1]
        # merge if adjacent (frames n and n+1 are neighbours) or overlapping
        if lo <= prev_hi + _D1:
            merged[-1] = (prev_lo, max(prev_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _gaps_in_range(lo: decimal.Decimal, hi: decimal.Decimal, coverage: list[_Interval]) -> list[_Interval]:
    """Return sub-intervals of [lo, hi] not covered by any entry in coverage.

    Gaps are returned in ascending order.
    """
    gaps: list[_Interval] = []
    cursor = lo
    for cov_lo, cov_hi in coverage:
        if cov_hi < lo:
            continue
        if cov_lo > hi:
            break
        if cursor < cov_lo:
            gaps.append((cursor, cov_lo - _D1))
        cursor = max(cursor, cov_hi + _D1)
        if cursor > hi:
            break
    if cursor <= hi:
        gaps.append((cursor, hi))
    return gaps


class FrameSet(BaseFrameSet):
    """
    A ``FrameSet`` is an immutable representation of the ordered, unique
    set of frames in a given frame range.

    The frame range can be expressed in the following ways:
        - 1-5
        - 1-5,10-20
        - 1-100x5 (every fifth frame)
        - 1-100y5 (opposite of above, fills in missing frames)
        - 1-100:4 (same as 1-100x4,1-100x3,1-100x2,1-100)
        - 1-2x0.333333 (subframes)

    A ``FrameSet`` is effectively an ordered frozenset, with
    FrameSet-returning versions of frozenset methods:

        >>> FrameSet('1-5').union(FrameSet('5-10'))
        FrameSet("1-10")
        >>> FrameSet('1-5').intersection(FrameSet('5-10'))
        FrameSet("5")

    Because a FrameSet is hashable, it can be used as the key to a dictionary:

        >>> d = {FrameSet("1-20"): 'good'}

    A FrameSet can be created from an iterable of frame numbers, and will
    construct an appropriate string representation:

        >>> FrameSet([1,2,3,4,5]).frange
        '1-5'
        >>> FrameSet([0, '0.1429', '0.2857', '0.4286', '0.5714', '0.7143', '0.8571', 1]).frange
        '0-1x0.142857'

    Caveats:
        1. Because the internal storage of a ``FrameSet`` contains the discreet
           values of the entire range, an exception will be thrown if the range
           exceeds a large reasonable limit, which could lead to huge memory
           allocations or memory failures. See ``fileseq.constants.MAX_FRAME_SIZE``.
        2. All frozenset operations return a normalized ``FrameSet``:
           internal frames are in numerically increasing order.
        3. Equality is based on the contents and order, NOT the frame range
           string (there are a finite, but potentially
           extremely large, number of strings that can represent any given range,
           only a "best guess" can be made).
        4. Human-created frame ranges (ie 1-100x5) will be reduced to the
           actual internal frames (ie 1-96x5).
        5. The "null" ``Frameset`` (``FrameSet('')``) is now a valid thing
           to create, it is required by set operations, but may cause confusion
           as both its start and end methods will raise IndexError.  The
           :meth:`is_null` property allows you to guard against this.

    Args:
        frange (str or FrameSet or collections.Iterable of str, int, float, or
            decimal.Decimal): the frame range as a string (ie "1-100x5") or
            iterable of frame numbers.

    Raises:
        :class:`.ParseException`: if the frame range
            (or a portion of it) could not be parsed.
        :class:`fileseq.exceptions.MaxSizeException`: if the range exceeds
            ``fileseq.constants.MAX_FRAME_SIZE``
    """
    FRANGE_RE = FRANGE_RE
    PAD_MAP = PAD_MAP
    PAD_RE = PAD_RE

    __slots__ = ('_frange', '_ranges', '_normalized_cache', '_hash_cache', '_has_subframes', '_subframe_type')

    _ranges: list[Range]
    _normalized_cache: list[Range] | None
    _hash_cache: int | None
    _has_subframes: bool
    _subframe_type: type[float] | type[decimal.Decimal] | None

    def __new__(cls, *args: typing.Any, **kwargs: typing.Any) -> FrameSet:
        """
        Initialize the :class:`FrameSet` object.

        Args:
            frange (str or :class:`FrameSet`): the frame range as a string (ie "1-100x5")

        Raises:
            :class:`.ParseException`: if the frame range
                (or a portion of it) could not be parsed.
            :class:`fileseq.exceptions.MaxSizeException`: if the range exceeds
                ``fileseq.constants.MAX_FRAME_SIZE``
        """
        self = super(cls, FrameSet).__new__(cls)
        return self

    def __init__(self, frange: FrameSetInput) -> None:
        """Initialize the :class:`FrameSet` object.
        """

        def catch_parse_err(fn, *a, **kw):  # type: ignore
            try:
                return fn(*a, **kw)
            except (TypeError, ValueError) as e:
                raise ParseException('FrameSet args parsing error: {}'.format(e)) from e

        # initialize caches
        self._normalized_cache = None
        self._hash_cache = None
        self._has_subframes = False
        self._subframe_type = None

        # if the user provides anything but a string, short-circuit the build
        if not isinstance(frange, (str,)):
            # if it's apparently a FrameSet already, short-circuit the build
            if set(dir(frange)).issuperset(self.__slots__):
                for attr in self.__slots__:
                    setattr(self, attr, getattr(frange, attr))
                return
            # if it's inherently disordered, sort and build
            elif isinstance(frange, Set):
                self._maxSizeCheck(frange)
                frames_raw = list(frange)
                # Normalize first
                frames = sorted(catch_parse_err(normalizeFrames, frames_raw))  # type: ignore
                # detect subframe type after normalization
                self._detect_subframe_type(frames)
                self._frange = catch_parse_err(  # type: ignore
                    self.framesToFrameRange, frames, sort=False, compress=False)
                self._ranges = self._frames_to_ranges(frames)
                return
            # if it's ordered, find unique and build
            elif isinstance(frange, Sized) and isinstance(frange, Iterable):
                self._maxSizeCheck(frange)
                # convert to list first to allow multiple iterations
                frange_list = list(frange)
                # normalize first
                normalized = catch_parse_err(normalizeFrames, frange_list)  # type: ignore
                # detect subframe type after normalization
                self._detect_subframe_type(normalized)
                seen_items: typing.Set[FrameValue] = set()
                order = list(unique(seen_items, normalized))  # type: ignore
                self._frange = catch_parse_err(  # type: ignore
                    self.framesToFrameRange, order, sort=False, compress=False)
                self._ranges = self._frames_to_ranges(order)
                return
            # if it's an individual number build directly
            elif isinstance(frange, (int, float, decimal.Decimal)):
                frame = normalizeFrame(frange)
                self._has_subframes = isinstance(frame, (float, decimal.Decimal)) and frame % 1 != 0
                self._frange = catch_parse_err(  # type: ignore
                    self.framesToFrameRange, [frame], sort=False, compress=False)
                frame_dec = decimal.Decimal(str(frame))
                self._ranges = [Range(frame_dec, frame_dec, decimal.Decimal(1))]
                return
            # in all other cases, cast to a string
            else:
                try:
                    frange = asString(frange)
                except Exception as err:
                    msg = 'Could not parse "{0}": cast to string raised: {1}'
                    raise ParseException(msg.format(frange, err))

        # we're willing to trim padding characters from consideration
        frange = str(frange)
        for key in self.PAD_MAP:
            frange = frange.replace(key, '')
        frange = ''.join(frange.split())
        self._frange = asString(frange)

        # because we're acting like a set, we need to support the empty set
        if not self._frange:
            self._ranges = []
            return

        # parse frame range into Range objects
        self._ranges = []
        maxSize = constants.MAX_FRAME_SIZE

        frange_parts: typing.List[typing.Any] = []
        frange_types: typing.List[typing.Any] = []
        has_decimal_notation = False
        for part in self._frange.split(","):
            if not part:
                continue
            start, end, modifier, chunk = self._parse_frange_part(part)
            frange_parts.append((start, end, modifier, chunk))
            frange_types.extend(map(type, (start, end, chunk)))
            if '.' in part:
                has_decimal_notation = True

        # determine best type for numbers in range
        FrameType: type[decimal.Decimal | int] = int
        if decimal.Decimal in frange_types or has_decimal_notation:
            FrameType = decimal.Decimal
            self._has_subframes = True

        for start, end, modifier, chunk in frange_parts:
            # convert to Decimal for Range storage
            start_dec = decimal.Decimal(str(start))
            end_dec = decimal.Decimal(str(end))
            chunk_dec = decimal.Decimal(str(chunk))

            # handle batched frames (1-100x5)
            if modifier == 'x':
                # calculate size mathematically without expansion
                range_size = int(abs(end_dec - start_dec) / abs(chunk_dec)) + 1
                self._maxSizeCheck(range_size + len(self))

                # check for overlap with existing ranges
                new_lo = min(start_dec, end_dec)
                new_hi = max(start_dec, end_dec)
                overlaps = any(
                    new_lo <= max(r.start, r.end) and new_hi >= min(r.start, r.end)
                    for r in self._ranges
                )

                if not overlaps:
                    actual_chunk = chunk_dec if end_dec >= start_dec else -chunk_dec
                    self._ranges.append(Range(start_dec, end_dec, actual_chunk))
                else:
                    frame_range = xfrange(start, end, chunk, maxSize=maxSize)
                    unique_frames: list[FrameValue] = [f for f in frame_range if f not in self]
                    if unique_frames:
                        self._ranges.extend(self._frames_to_ranges(unique_frames))
                        
            # handle staggered frames (1-100:5)
            elif modifier == ':':
                if '.' in str(chunk):
                    raise ValueError("Unable to stagger subframes")
                # staggered frames must be expanded
                frames = []
                seen = set(self)  # track what's already in the frameset
                for stagger in range(chunk, 0, -1):
                    frame_range = xfrange(start, end, stagger, maxSize=maxSize)
                    for f in frame_range:
                        if f not in seen:
                            frames.append(f)
                            seen.add(f)  # mark as seen to avoid duplicates within stagger
                self._maxSizeCheck(len(frames) + len(self))
                if frames:
                    self._ranges.extend(self._frames_to_ranges(frames))
                    
            # handle filled frames (1-100y5)
            elif modifier == 'y':
                if '.' in str(chunk):
                    raise ValueError("Unable to fill subframes")
                # filled frames must be expanded
                not_good = frozenset(xfrange(start, end, chunk, maxSize=maxSize))
                all_frames = xfrange(start, end, 1, maxSize=maxSize)
                frames = [f for f in all_frames if f not in not_good and f not in self]
                self._maxSizeCheck(len(frames) + len(self))
                if frames:
                    self._ranges.extend(self._frames_to_ranges(frames))
                    
            # handle full ranges and single frames
            else:
                # calculate size mathematically without expansion
                range_size = int(abs(end_dec - start_dec)) + 1
                self._maxSizeCheck(range_size + len(self))

                # check for overlap with existing ranges
                new_lo = min(start_dec, end_dec)
                new_hi = max(start_dec, end_dec)
                overlaps = any(
                    new_lo <= max(r.start, r.end) and new_hi >= min(r.start, r.end)
                    for r in self._ranges
                )

                actual_step = decimal.Decimal(1) if start < end else decimal.Decimal(-1)
                if not overlaps:
                    self._ranges.append(Range(start_dec, end_dec, actual_step))
                elif _all_ranges_contiguous(self._ranges):
                    # fast path: all existing ranges are step-1 or step-(-1), so we can
                    # compute the uncovered sub-intervals directly without per-frame iteration
                    coverage = _merged_coverage(self._ranges)
                    gaps = _gaps_in_range(new_lo, new_hi, coverage)
                    if actual_step < _D0:
                        # descending: append gaps in reverse so frame order matches start→end
                        for gap_lo, gap_hi in reversed(gaps):
                            self._ranges.append(Range(gap_hi, gap_lo, actual_step))
                    else:
                        for gap_lo, gap_hi in gaps:
                            self._ranges.append(Range(gap_lo, gap_hi, actual_step))
                else:
                    istep = 1 if start < end else -1
                    frame_range = xfrange(start, end, istep, maxSize=maxSize)
                    unique_frames2: list[FrameValue] = [f for f in frame_range if f not in self]
                    if unique_frames2:
                        self._ranges.extend(self._frames_to_ranges(unique_frames2))

    @property
    def is_null(self) -> bool:
        """
        Read-only access to determine if the :class:`FrameSet` is the null or
        empty :class:`FrameSet`.

        Returns:
            bool:
        """
        return not (self._frange and self._ranges)

    @property
    def frange(self) -> str:
        """
        Read-only access to the frame range used to create this :class:`FrameSet`.

        Returns:
            str:
        """
        return self._frange or ''

    @property
    def items(self) -> frozenset[FrameValue]:
        """
        Read-only access to the unique frames that form this :class:`FrameSet`.
        
        .. deprecated:: 3.0
            Direct access to `.items` triggers full expansion of the frame range.
            For large ranges, prefer iteration: `for frame in frameset` or 
            membership testing: `frame in frameset`.

        Returns:
            frozenset:
        """
        warnings.warn(
            "FrameSet.items triggers full frame expansion. "
            "For large ranges, use iteration or membership testing instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return frozenset(self)

    @property
    def order(self) -> tuple[FrameValue, ...]:
        """
        Read-only access to the ordered frames that form this :class:`FrameSet`.
        
        .. deprecated:: 3.0
            Direct access to `.order` triggers full expansion of the frame range.
            For large ranges, prefer iteration: `for frame in frameset` or 
            indexing: `frameset[i]`.

        Returns:
            tuple:
        """
        warnings.warn(
            "FrameSet.order triggers full frame expansion. "
            "For large ranges, use iteration or indexing instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return tuple(self)

    @classmethod
    def from_iterable(cls, frames: typing.Iterable[FrameValue], sort: bool = False) -> FrameSet:
        """
        Build a :class:`FrameSet` from an iterable of frames.

        Args:
            frames (collections.Iterable): an iterable object containing frames as integers
            sort (bool): True to sort frames before creation, default is False

        Returns:
            :class:`FrameSet`:
        """
        return FrameSet(sorted(frames) if sort else frames)

    def _detect_subframe_type(self, frames: typing.Iterable[FrameValue]) -> None:
        """Detect and set subframe type from frame values"""
        for f in frames:
            if isinstance(f, float) and f % 1 != 0:
                self._has_subframes = True
                self._subframe_type = float
                return
            elif isinstance(f, decimal.Decimal) and f % 1 != 0:
                self._has_subframes = True
                self._subframe_type = decimal.Decimal
                return

    @staticmethod
    def _frames_to_ranges(frames: typing.List[FrameValue]) -> list[Range]:
        """Convert a list of frames to a list of Range objects"""
        if not frames:
            return []
        
        ranges: list[Range] = []
        start_frame = decimal.Decimal(str(frames[0]))
        prev_frame = start_frame
        step: decimal.Decimal | None = None
        
        for frame in frames[1:]:
            curr_frame = decimal.Decimal(str(frame))
            curr_step = curr_frame - prev_frame
            
            if step is None:
                step = curr_step
            elif step != curr_step:
                # end current range
                ranges.append(Range(start_frame, prev_frame, step))
                start_frame = curr_frame
                step = None
            
            prev_frame = curr_frame
        
        # add final range
        if step is None:
            step = decimal.Decimal(1)
        ranges.append(Range(start_frame, prev_frame, step))
        
        return ranges

    @classmethod
    def from_range(cls, start: int, end: int, step: int = 1) -> FrameSet:
        """
        Build a :class:`FrameSet` from given start and end frames (inclusive).

        Args:
            start (int): The first frame of the :class:`FrameSet`.
            end (int): The last frame of the :class:`FrameSet`.
            step (int, optional): Range step (default 1).

        Returns:
            :class:`FrameSet`:
        """
        # match range() exception
        if not isinstance(step, int):
            raise TypeError("integer step argument expected, got {}."
                            .format(type(step)))
        elif step == 0:
            raise ValueError("step argument must not be zero")
        elif step == 1:
            fstart, fend = normalizeFrames([start, end])
            range_str = "{0}-{1}".format(fstart, fend)
        else:
            fstart, fend = normalizeFrames([start, end])
            fstep = normalizeFrame(step)
            range_str = "{0}-{1}x{2}".format(fstart, fend, fstep)

        return FrameSet(range_str)

    @classmethod
    def _cast_to_frameset(cls, other: typing.Any) -> FrameSet:
        """
        Private method to simplify comparison operations.

        Args:
            other (:class:`FrameSet` or set or frozenset or iterable): item to be compared

        Returns:
            :class:`FrameSet`

        Raises:
            :class:`NotImplemented`: if a comparison is impossible
        """
        if isinstance(other, FrameSet):
            return other
        try:
            return FrameSet(other)
        except Exception:
            return NotImplemented  # type: ignore

    def index(self, frame: int) -> int:
        """
        Return the index of the given frame number within the :class:`FrameSet`.

        Args:
            frame (int): the frame number to find the index for

        Returns:
            int:

        Raises:
            :class:`ValueError`: if frame is not in self
        """
        idx = 0
        for r in self._ranges:
            if frame in r:
                # find position within this range
                frame_dec = decimal.Decimal(str(frame))
                offset = abs(frame_dec - r.start)
                return idx + int(offset / abs(r.step))
            idx += len(r)
        raise ValueError(f"{frame} is not in FrameSet")

    def frame(self, index: int) -> FrameValue:
        """
        Return the frame at the given index.

        Args:
            index (int): the index to find the frame for

        Returns:
            int:

        Raises:
            :class:`IndexError`: if index is out of bounds
        """
        if index < 0:
            index = len(self) + index
        if index < 0 or index >= len(self):
            raise IndexError("index out of range")
        
        curr_idx = 0
        for r in self._ranges:
            range_len = len(r)
            if curr_idx + range_len > index:
                # frame is in this range
                offset = index - curr_idx
                frame = r.start + (r.step * offset)
                return int(frame) if frame % 1 == 0 else frame
            curr_idx += range_len
        
        raise IndexError("index out of range")

    def hasFrame(self, frame: int) -> bool:
        """
        Check if the :class:`FrameSet` contains the frame or subframe

        Args:
            frame (int): the frame number to search for

        Returns:
            bool:
        """
        return frame in self

    def hasSubFrames(self) -> bool:
        """
        Check if the :class:`FrameSet` contains any subframes

        Returns:
            bool:

        """
        if self._has_subframes:
            return True
        for r in self._ranges:
            if r.start % 1 != 0 or r.end % 1 != 0 or r.step % 1 != 0:
                self._has_subframes = True
                return True
        return False

    def start(self) -> FrameValue:
        """
        The first frame in the :class:`FrameSet`.

        Returns:
            int:

        Raises:
            :class:`IndexError`: (with the empty :class:`FrameSet`)
        """
        if not self._ranges:
            raise IndexError("FrameSet is empty")
        frame = self._ranges[0].start
        return int(frame) if frame % 1 == 0 else frame

    def end(self) -> FrameValue:
        """
        The last frame in the :class:`FrameSet`.

        Returns:
            int:

        Raises:
            :class:`IndexError`: (with the empty :class:`FrameSet`)
        """
        if not self._ranges:
            raise IndexError("FrameSet is empty")
        r = self._ranges[-1]
        # actual last frame is start + step * (len - 1), not necessarily r.end
        frame = r.start + r.step * (len(r) - 1)
        return int(frame) if frame % 1 == 0 else frame

    def isConsecutive(self) -> bool:
        """
        Return whether the frame range represents consecutive integers,
        as opposed to having a stepping >= 2

        Examples:
            >>> FrameSet('1-100').isConsecutive()
            True
            >>> FrameSet('1-100x2').isConsecutive()
            False
            >>> FrameSet('1-50,60-100').isConsecutive()
            False

        Returns:
            bool:
        """
        if self.hasSubFrames():
            return False
        
        if not self._ranges:
            return False
        
        # Each range must have step=1 or step=-1 (no skipping)
        for r in self._ranges:
            if abs(r.step) != 1:
                return False

        # Track covered [lo, hi] as ranges are visited in order.
        # A new range may extend lo or hi, but only if it doesn't
        # introduce a gap and doesn't extend in both directions.
        lo = hi = None
        extended_lo = extended_hi = False

        for r in self._ranges:
            r_lo = int(min(r.start, r.end))
            r_hi = int(max(r.start, r.end))

            if lo is None:
                lo, hi = r_lo, r_hi
                continue

            assert lo is not None
            assert hi is not None
            # Must overlap or be adjacent to current covered range
            if r_lo > hi + 1 or r_hi < lo - 1:
                return False

            if r_lo < lo:
                if extended_hi:
                    return False
                extended_lo = True
            if r_hi > hi:
                if extended_lo:
                    return False
                extended_hi = True

            lo = min(lo, r_lo)  # type: ignore[type-var]
            hi = max(hi, r_hi)  # type: ignore[type-var]

        return True

    def frameRange(self, zfill: int = 0, decimal_places: int | None = None) -> str:
        """
        Return the frame range used to create this :class:`FrameSet`, padded if
        desired.

        Examples:
            >>> FrameSet('1-100').frameRange()
            '1-100'
            >>> FrameSet('1-100').frameRange(5)
            '00001-00100'
            >>> FrameSet('1-100').frameRange(0, 1)
            '1.0-100.0'
            >>> FrameSet('1.0-100.0').frameRange()
            '1.0-100.0'

        Args:
            zfill (int): the width to use to zero-pad the frame range string
            decimal_places (int or None): the number of decimal places to use
                in frame range string

        Returns:
            str:
        """
        return self.padFrameRange(self.frange, zfill, decimal_places)

    def invertedFrameRange(self, zfill: int = 0, decimal_places: int | None = None) -> str:
        """
        Return the inverse of the :class:`FrameSet` 's frame range, padded if
        desired.
        The inverse is every frame within the full extent of the range.

        Examples:
            >>> FrameSet('1-100x2').invertedFrameRange()
            '2-98x2'
            >>> FrameSet('1-100x2').invertedFrameRange(5)
            '00002-00098x2'

        If the inverted frame size exceeds ``fileseq.constants.MAX_FRAME_SIZE``,
        a ``MaxSizeException`` will be raised.

        Args:
            zfill (int): the width to use to zero-pad the frame range string
            decimal_places (int or None): the number of decimal places to use in
                frame range string

        Returns:
            str:

        Raises:
            :class:`fileseq.exceptions.MaxSizeException`:
        """
        # No inverted frame range when range includes subframes
        if self.hasSubFrames():
            return ''

        result: list[FrameValue] = []
        frames = sorted(int(f) for f in self)
        for idx, frame in enumerate(frames[:-1]):
            next_frame = frames[idx + 1]
            if next_frame - frame != 1:
                r = range(frame + 1, next_frame)
                self._maxSizeCheck(len(r) + len(result))
                result += r  # type: ignore[arg-type]

        if not result:
            return ''

        return self.framesToFrameRange(
            result, zfill=zfill, sort=False, compress=False)

    def normalize(self) -> FrameSet:
        """
        Returns a new normalized (sorted and compacted) :class:`FrameSet`.

        Returns:
            :class:`FrameSet`:
        """
        if self._normalized_cache is None:
            self._normalized_cache = self._normalize()
        # create new FrameSet from normalized ranges
        fs = self.__class__.__new__(self.__class__)
        fs._ranges = self._normalized_cache[:]
        fs._normalized_cache = fs._ranges[:]
        fs._hash_cache = None
        fs._has_subframes = self._has_subframes
        fs._subframe_type = self._subframe_type
        fs._frange = FrameSet.framesToFrameRange(fs, sort=False, compress=False)
        return fs

    @overload
    def batches(self, batch_size: int, frames: typing.Literal[True]) -> typing.Iterator[_islice[FrameValue]]:
        ...

    @overload
    def batches(self, batch_size: int, frames: typing.Literal[False] = ...) -> typing.Iterator[FrameSet]:
        ...

    def batches(self, batch_size: int, frames: bool = False) -> typing.Iterator[_islice[FrameValue]] | typing.Iterator[FrameSet]:
        """
        Returns a generator that yields sub-batches of frames, up to ``batch_size``.
        If ``frames=False``, each batch is a new ``FrameSet`` subrange.
        If ``frames=True``, each batch is an islice generator object of the sub-range.

        Args:
            batch_size (int): max frame values in each batch
            frames (bool): if True, generate islice sub-ranges instead of FrameSets

        Returns:
            generator: yields batches of islice or FrameSet sub-ranges
        """
        batch_it = batchIterable(self, batch_size)
        if frames:
            # They just want batches of the frame values
            return batch_it

        # return batches of FrameSet instance
        return (self.from_iterable(b) for b in batch_it)

    def __getstate__(self) -> tuple[str]:
        """
        Allows for serialization to a pickled :class:`FrameSet`.

        Returns:
            tuple: (frame range string,
        """
        # we have to special-case the empty FrameSet, because of a quirk in
        # Python where __setstate__ will not be called if the return value of
        # bool(__getstate__) == False.  A tuple with ('',) will return True.
        return (self.frange,)

    def __setstate__(self, state: typing.Any) -> None:
        """
        Allows for de-serialization from a pickled :class:`FrameSet`.

        Args:
            state (tuple or str or dict): A string/dict can be used for
                backwards compatibility

        Raises:
            ValueError: if state is not an appropriate type
        """
        if isinstance(state, tuple):
            # this is to allow unpickling of "3rd generation" FrameSets,
            # which are immutable and may be empty.
            self.__init__(state[0])  # type: ignore[misc]
        elif isinstance(state, str):
            # this is to allow unpickling of "2nd generation" FrameSets,
            # which were mutable and could not be empty.
            self.__init__(state)  # type: ignore[misc]
        elif isinstance(state, dict):
            # this is to allow unpickling of "1st generation" FrameSets,
            # when the full __dict__ was stored
            if '__frange' in state:
                # Old format - reconstruct from frange
                self.__init__(state['__frange'])  # type: ignore[misc]
            elif '_frange' in state:
                # Reconstruct from frange
                self.__init__(state['_frange'])  # type: ignore[misc]
            else:
                msg = "Unrecognized state data from which to deserialize FrameSet"
                raise ValueError(msg)
        else:
            msg = "Unrecognized state data from which to deserialize FrameSet"
            raise ValueError(msg)

    def __getitem__(self, index: int | slice) -> FrameValue | FrameSet:
        """
        Allows indexing into the ordered frames of this :class:`FrameSet`.

        Args:
            index (int or slice): the index to retrieve

        Returns:
            int or FrameSet:

        Raises:
            :class:`IndexError`: if index is out of bounds
        """
        if isinstance(index, slice):
            # handle slicing without full expansion
            start, stop, step = index.indices(len(self))
            frames = [self.frame(i) for i in range(start, stop, step)]
            return self.from_iterable(frames)
        return self.frame(index)

    def __len__(self) -> int:
        """
        Returns the length of the ordered frames of this :class:`FrameSet`.

        Returns:
            int:
        """
        return sum(len(r) for r in self._ranges)

    def __str__(self) -> str:
        """
        Returns the frame range string of this :class:`FrameSet`.

        Returns:
            str:
        """
        return self.frange

    def __repr__(self) -> str:
        """
        Returns a long-form representation of this :class:`FrameSet`.

        Returns:
            str:
        """
        return '{0}("{1}")'.format(self.__class__.__name__, self.frange)

    def __iter__(self) -> typing.Iterator[FrameValue]:
        """
        Allows for iteration over the ordered frames of this :class:`FrameSet`.

        Returns:
            generator:
        """
        for r in self._ranges:
            for frame in r:
                # convert to appropriate type based on FrameSet's subframe type
                if self._has_subframes:
                    if self._subframe_type == float:
                        yield float(frame)
                    else:
                        # decimal type
                        yield frame if isinstance(frame, decimal.Decimal) else decimal.Decimal(frame)
                else:
                    # integer-only FrameSet
                    yield int(frame) if isinstance(frame, decimal.Decimal) else frame

    def __reversed__(self) -> typing.Iterator[FrameValue]:
        """
        Allows for reversed iteration over the ordered frames of this
        :class:`FrameSet`.

        Returns:
            generator:
        """
        for r in reversed(self._ranges):
            frames = list(r)
            yield from reversed(frames)

    def __contains__(self, item: object) -> bool:
        """
        Check if item is a member of this :class:`FrameSet`.

        Args:
            item (int): the frame number to check for

        Returns:
            bool:
        """
        for r in self._ranges:
            if item in r:  # type: ignore[operator]
                return True
        return False

    def _normalize(self) -> list[Range]:
        """Normalize ranges by expanding, sorting, and compacting"""
        # expand all frames
        all_frames = list(self)
        if not all_frames:
            return []
        # sort frames
        all_frames.sort()
        # compact back to ranges
        return self._frames_to_ranges(all_frames)

    def __hash__(self) -> int:
        """
        Builds the hash of this :class:`FrameSet` for equality checking and to
        allow use as a dictionary key.

        Returns:
            int:
        """
        if self._hash_cache is None:
            if self._normalized_cache is None:
                self._normalized_cache = self._normalize()
            self._hash_cache = hash(tuple(
                (r.start, r.end, r.step) for r in self._normalized_cache
            ))
        return self._hash_cache

    def __lt__(self, other: object) -> typing.Any:
        """
        Check if self < other via a comparison of the contents. If other is not
        a :class:`FrameSet`, but is a set, frozenset, or is iterable, it will be
        cast to a :class:`FrameSet`.

        Note:

            A :class:`FrameSet` is less than other if the set of its contents are
            less, OR if the contents are equal but the order of the items is less.

            .. code-block:: python
                :caption: Same contents, but (1,2,3,4,5) sorts below (5,4,3,2,1)

                >>> FrameSet("1-5") < FrameSet("5-1")
                True

        Args:
            other (:class:`FrameSet`): Can also be an object that can be cast to a :class:`FrameSet`

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        
        # check if proper subset
        is_subset = all(f in other for f in self)
        if is_subset and len(self) < len(other):
            return True
        
        # same size, compare order lexicographically
        if len(self) == len(other):
            for a, b in zip(self, other):
                if a != b:
                    return a < b
        
        return False

    def __le__(self, other: object) -> typing.Any:
        """
        Check if `self` <= `other` via a comparison of the contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        Args:
            other (:class:`FrameSet`): Also accepts an object that can be cast to a :class:`FrameSet`

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.issubset(other)

    def __eq__(self, other: object) -> typing.Any:
        """
        Check if `self` == `other` via a comparison of the hash of
        their contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        Args:
            other (:class:`FrameSet`): Also accepts an object that can be cast to a :class:`FrameSet`

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        if not isinstance(other, FrameSet):
            if not isinstance(other, typing.Iterable):
                return NotImplemented
            other = self.from_iterable(other)
        
        # normalize both on first comparison, cache forever
        if self._normalized_cache is None:
            self._normalized_cache = self._normalize()
        if other._normalized_cache is None:
            other._normalized_cache = other._normalize()
        
        return self._normalized_cache == other._normalized_cache

    def __ne__(self, other: object) -> typing.Any:
        """
        Check if `self` != `other` via a comparison of the hash of
        their contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        Args:
            other (:class:`FrameSet`): Also accepts an object that can be cast to a :class:`FrameSet`

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        is_equals = self == other
        if is_equals != NotImplemented:
            return not is_equals
        return is_equals

    def __ge__(self, other: object) -> typing.Any:
        """
        Check if `self` >= `other` via a comparison of the contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        Args:
            other (:class:`FrameSet`): Also accepts an object that can be cast to a :class:`FrameSet`

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.issuperset(other)

    def __gt__(self, other: object) -> typing.Any:
        """
        Check if `self` > `other` via a comparison of the contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        Note:
           A :class:`FrameSet` is greater than `other` if the set of its
           contents are greater,
           OR if the contents are equal but the order is greater.

           .. code-block:: python
               :caption: Same contents, but (1,2,3,4,5) sorts below (5,4,3,2,1)

               >>> FrameSet("1-5") > FrameSet("5-1")
               False

        Args:
            other (:class:`FrameSet`): Also accepts an object that can be cast to a :class:`FrameSet`

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        
        # check if proper superset
        is_superset = all(f in self for f in other)
        if is_superset and len(self) > len(other):
            return True
        
        # same size, compare order lexicographically
        if len(self) == len(other):
            for a, b in zip(self, other):
                if a != b:
                    return a > b
        
        return False

    def __and__(self, other: object) -> typing.Any:
        """
        Overloads the ``&`` operator.
        Returns a new :class:`FrameSet` that holds only the
        frames `self` and `other` have in common.

        Note:

            The order of operations is irrelevant:
            ``(self & other) == (other & self)``

        Args:
            other (:class:`FrameSet`):

        Returns:
            :class:`FrameSet`:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        # iterate and check membership without expanding
        result = [f for f in self if f in other]
        return self.from_iterable(result)

    __rand__ = __and__

    def __sub__(self, other: object) -> typing.Any:
        """
        Overloads the ``-`` operator.
        Returns a new :class:`FrameSet` that holds only the
        frames of `self` that are not in `other.`

        Note:

            This is for left-hand subtraction (``self - other``).

        Args:
            other (:class:`FrameSet`):

        Returns:
            :class:`FrameSet`:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        # iterate and check membership without expanding
        result = [f for f in self if f not in other]
        return self.from_iterable(result)

    def __rsub__(self, other: object) -> typing.Any:
        """
        Overloads the ``-`` operator.
        Returns a new :class:`FrameSet` that holds only the
        frames of `other` that are not in `self.`

        Note:

            This is for right-hand subtraction (``other - self``).

        Args:
            other (:class:`FrameSet`):

        Returns:
            :class:`FrameSet`:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        # iterate and check membership without expanding
        result = [f for f in other if f not in self]
        return self.from_iterable(result)

    def __or__(self, other: object) -> typing.Any:
        """
        Overloads the ``|`` operator.
        Returns a new :class:`FrameSet` that holds all the
        frames in `self,` `other,` or both.

        Note:

            The order of operations is irrelevant:
            ``(self | other) == (other | self)``

        Args:
            other (:class:`FrameSet`):

        Returns:
            :class:`FrameSet`:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        # combine both without expanding, iterate and deduplicate
        seen = set()
        result = []
        for f in self:
            if f not in seen:
                seen.add(f)
                result.append(f)
        for f in other:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return self.from_iterable(result, sort=True)

    __ror__ = __or__

    def __xor__(self, other: object) -> typing.Any:
        """
        Overloads the ``^`` operator.
        Returns a new :class:`FrameSet` that holds all the
        frames in `self` or `other` but not both.

        Note:
            The order of operations is irrelevant:
            ``(self ^ other) == (other ^ self)``

        Args:
            other (:class:`FrameSet`):

        Returns:
            :class:`FrameSet`:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        # frames in self but not other, plus frames in other but not self
        result = [f for f in self if f not in other]
        result.extend(f for f in other if f not in self)
        return self.from_iterable(result, sort=True)

    __rxor__ = __xor__

    def isdisjoint(self, other: typing.Any) -> bool | NotImplemented:  # type: ignore
        """
        Check if the contents of :class:self has no common intersection with the
        contents of :class:other.

        Args:
            other (:class:`FrameSet`):

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented  # type: ignore
        # check if any frame in self is in other
        for f in self:
            if f in other:
                return False
        return True

    def issubset(self, other: typing.Any) -> bool | NotImplemented:  # type: ignore
        """
        Check if the contents of `self` is a subset of the contents of
        `other.`

        Args:
            other (:class:`FrameSet`):

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented  # type: ignore
        # check if all frames in self are in other
        for f in self:
            if f not in other:
                return False
        return True

    def issuperset(self, other: typing.Any) -> bool | NotImplemented:  # type: ignore
        """
        Check if the contents of `self` is a superset of the contents of
        `other.`

        Args:
            other (:class:`FrameSet`):

        Returns:
            bool:
            :class:`NotImplemented`: if `other` fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented  # type: ignore
        # check if all frames in other are in self
        for f in other:
            if f not in self:
                return False
        return True

    def union(self, *other: typing.Iterable[FrameValue]) -> FrameSet:
        """
        Returns a new :class:`FrameSet` with the elements of `self` and
        of `other`.

        Args:
            other (:class:`FrameSet`): or objects that can cast to :class:`FrameSet`

        Returns:
            :class:`FrameSet`:
        """
        seen = set()
        result = []
        for f in self:
            if f not in seen:
                seen.add(f)
                result.append(f)
        for o in other:
            for f in o:
                if f not in seen:
                    seen.add(f)
                    result.append(f)
        return self.from_iterable(result, sort=True)

    def intersection(self, *other: typing.Iterable[FrameValue]) -> FrameSet:
        """
        Returns a new :class:`FrameSet` with the elements common to `self` and
        `other`.

        Args:
            other (:class:`FrameSet`): or objects that can cast to :class:`FrameSet`

        Returns:
            :class:`FrameSet`:
        """
        result = list(self)
        for o in other:
            o_set = set(o)
            result = [f for f in result if f in o_set]
        return self.from_iterable(result)

    def difference(self, *other: typing.Iterable[FrameValue]) -> FrameSet:
        """
        Returns a new :class:`FrameSet` with elements in `self` but not in
        `other`.

        Args:
            other (:class:`FrameSet`): or objects that can cast to :class:`FrameSet`

        Returns:
            :class:`FrameSet`:
        """
        exclude: set[FrameValue] = set()
        for o in other:
            exclude.update(o)
        result = [f for f in self if f not in exclude]
        return self.from_iterable(result)

    def symmetric_difference(self, other: typing.Any) -> FrameSet:
        """
        Returns a new :class:`FrameSet` that contains all the elements in either
        `self` or `other`, but not both.

        Args:
            other (:class:`FrameSet`):

        Returns:
            :class:`FrameSet`:
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented  # type: ignore
        # frames in self but not other, plus frames in other but not self
        result = [f for f in self if f not in other]
        result.extend(f for f in other if f not in self)
        return self.from_iterable(result, sort=True)

    def copy(self) -> FrameSet:
        """
        Create a deep copy of this :class:`FrameSet`.

        Returns:
            :class:`.FrameSet`:
        """
        fs = self.__class__.__new__(self.__class__)
        fs._frange = self._frange
        fs._ranges = self._ranges[:]
        fs._normalized_cache = self._normalized_cache[:] if self._normalized_cache else None
        fs._hash_cache = self._hash_cache
        fs._has_subframes = self._has_subframes
        fs._subframe_type = self._subframe_type
        return fs

    @classmethod
    def _maxSizeCheck(cls, obj: int | float | decimal.Decimal | Sized | typing.Any) -> None:
        """
        Raise a MaxSizeException if ``obj`` exceeds MAX_FRAME_SIZE

        Args:
            obj (numbers.Number or collection):

        Raises:
            :class:`fileseq.exceptions.MaxSizeException`:
        """
        fail = False
        size = 0

        if isinstance(obj, numbers.Number):
            if obj > constants.MAX_FRAME_SIZE:  # type: ignore
                fail = True
                size = obj  # type: ignore

        elif hasattr(obj, '__len__'):
            size = len(obj)
            fail = size > constants.MAX_FRAME_SIZE

        if fail:
            raise MaxSizeException('Frame size %s > %s (MAX_FRAME_SIZE)'
                                   % (size, constants.MAX_FRAME_SIZE))

    @classmethod
    def isFrameRange(cls, frange: str) -> bool:
        """
        Return True if the given string is a frame range. Any padding
        characters, such as '#' and '@' are ignored.

        Args:
            frange (str): a frame range to test

        Returns:
            bool:
        """
        # we're willing to trim padding characters from consideration
        # this translation is orders of magnitude faster than prior method
        frange = str(frange)
        for key in cls.PAD_MAP:
            frange = frange.replace(key, '')

        if not frange:
            return True

        for part in asString(frange).split(','):
            if not part:
                continue
            try:
                cls._parse_frange_part(part)
            except ParseException:
                return False

        return True

    @classmethod
    def padFrameRange(cls, frange: str, zfill: int, decimal_places: int | None = None) -> str:
        """
        Return the zero-padded version of the frame range string.

        Args:
            frange (str): a frame range to test
            zfill (int):
            decimal_places (int or None):

        Returns:
            str:
        """

        def _do_pad(match: typing.Any) -> str:
            """
            Substitutes padded for unpadded frames.
            """
            result = list(match.groups())

            neg, start = result[:2]
            result[:2] = [pad(neg + start, zfill, decimal_places)]

            neg, end = result[2:4]
            if end:
                result[2:4] = [pad(neg + end, zfill, decimal_places)]

            return ''.join((i for i in result if i))

        return cls.PAD_RE.sub(_do_pad, frange)

    @classmethod
    def _parse_frange_part(cls, frange: str) -> tuple[int, int, str, int]:
        """
        Internal method: parse a discrete frame range part.

        Args:
            frange (str): single part of a frame range as a string
                (ie "1-100x5")

        Returns:
            tuple: (start, end, modifier, chunk)

        Raises:
            :class:`.ParseException`: if the frame range can
                not be parsed
        """
        match = cls.FRANGE_RE.match(frange)
        if not match:
            msg = 'Could not parse "{0}": did not match {1}'
            raise ParseException(msg.format(frange, cls.FRANGE_RE.pattern))
        start, end, modifier, chunk = match.groups()
        start = normalizeFrame(start)
        end = normalizeFrame(end) if end is not None else start
        chunk = normalizeFrame(chunk) if chunk is not None else 1

        if end > start and chunk is not None and chunk < 0:  # type: ignore[operator]
            msg = 'Could not parse "{0}: chunk can not be negative'
            raise ParseException(msg.format(frange))

        # a zero chunk is just plain illogical
        if chunk == 0:
            msg = 'Could not parse "{0}": chunk cannot be 0'
            raise ParseException(msg.format(frange))

        return start, end, modifier, abs(chunk)  # type: ignore

    @staticmethod
    def _build_frange_part(start: object, stop: object, stride: FrameValue | None, zfill: int = 0) -> str:
        """
        Private method: builds a proper and padded frame range string.

        Args:
            start (int or decimal.Decimal): first frame
            stop (int or or decimal.Decimal or None): last frame
            stride (int or None): increment
            zfill (int): width for zero padding

        Returns:
            str:
        """
        if stop is None:
            return ''
        pad_start = pad(start, zfill)
        pad_stop = pad(stop, zfill)
        if stride is None or start == stop:
            return '{0}'.format(pad_start)
        elif abs(stride) == 1:
            return '{0}-{1}'.format(pad_start, pad_stop)
        else:
            stride = normalizeFrame(stride)
            return '{0}-{1}x{2}'.format(pad_start, pad_stop, stride)

    @staticmethod
    def _build_frange_part_decimal(
            start: decimal.Decimal,
            stop: decimal.Decimal,
            count: int,
            stride: decimal.Decimal | None,
            min_stride: decimal.Decimal,
            max_stride: decimal.Decimal,
            zfill: int = 0
        ) -> str:
        """
        Private method: builds a proper and padded subframe range string from
        decimal values.

        Args:
            start (decimal.Decimal): first frame
            stop (decimal.Decimal): last frame
            count (int): number of frames in range (inclusive)
            stride (decimal.Decimal or None): stride to use if known else None
            min_stride (decimal.Decimal): minimum increment that will produce
                correctly rounded frames
            max_stride (decimal.Decimal): maximum increment that will produce
                correctly rounded frames
            zfill (int): width for zero padding

        Returns:
            str:
        """
        if stride is None:
            # Use an exact stride value if within allowed limits for
            # range, otherwise use midpoint of stride limits
            stride = (stop - start) / (count - 1)
            if not min_stride <= stride <= max_stride:
                stride = (min_stride + max_stride) / 2

            # Minimise number of decimal places in stride
            stride_range = max_stride - min_stride
            stride_range_tup = stride_range.as_tuple()
            leading_zeros = abs(len(stride_range_tup.digits) + int(stride_range_tup.exponent))
            stride = abs(quantize(stride, leading_zeros + 1)).normalize()

        assert isinstance(stride, decimal.Decimal)

        # Adjust end frame if required so correct number of steps is
        # calculated when recreating FrameSet from frange string
        while abs(stop - start) / stride + 1 < count:
            exponent = int(stop.as_tuple().exponent)
            delta = decimal.Decimal(1).scaleb(exponent)
            stop += delta.copy_sign(stop)

        start, stop = normalizeFrames([start, stop])  # type:ignore[assignment]
        return FrameSet._build_frange_part(start, stop, stride, zfill=zfill)

    @staticmethod
    def _framesToFrameRangesFloat(
            frames: list[int | float],
            zfill: int = 0
        ) -> typing.Iterator[str]:
        """
        Converts a sequence of int/float frames to a series of padded
        frame range strings.

        Args:
            frames (list[int | float]): sequence of frames to process
            zfill (int): width for zero padding

        Yields:
            str:
        """
        _build = FrameSet._build_frange_part

        curr_start: int | float | None = None
        curr_stride: int | float | None = None
        curr_frame: int | float
        last_frame: int | float | None = None
        curr_count = 0

        if not frames:
            return

        for curr_frame in frames:
            if curr_start is None:
                curr_start = curr_frame
                last_frame = curr_frame
                curr_count += 1
                continue
            if curr_stride is None:
                curr_stride = abs(curr_frame - curr_start)
            assert last_frame is not None
            new_stride = abs(curr_frame - last_frame)

            if curr_stride == new_stride:
                curr_count += 1
            elif curr_count == 2 and curr_stride != 1:
                yield _build(curr_start, curr_start, None, zfill)
                curr_start = last_frame
                curr_stride = new_stride
            else:
                yield _build(curr_start, last_frame, curr_stride, zfill)
                curr_stride = None
                curr_start = curr_frame
                curr_count = 1

            last_frame = curr_frame

        if curr_count == 2 and curr_stride != 1:
            yield _build(curr_start, curr_start, None, zfill)
            yield _build(curr_frame, curr_frame, None, zfill)
        else:
            yield _build(curr_start, curr_frame, curr_stride, zfill)

    @staticmethod
    def _framesToFrameRangesDecimal(
            frames: list[decimal.Decimal],
            zfill: int = 0
        ) -> typing.Iterator[str]:
        """
        Converts a sequence of Decimal frames to a series of padded
        frame range strings.

        Args:
            frames (list[decimal.Decimal]): sequence of frames to process
            zfill (int): width for zero padding

        Yields:
            str:
        """
        _build = FrameSet._build_frange_part
        _build_decimal = FrameSet._build_frange_part_decimal

        curr_start: decimal.Decimal | None = None
        curr_stride: decimal.Decimal | None = None
        curr_strides: set[decimal.Decimal]  = set()
        curr_min_stride: decimal.Decimal | None = None
        curr_max_stride: decimal.Decimal | None = None
        curr_frame: decimal.Decimal
        last_frame: decimal.Decimal | None = None
        curr_count = 0

        if not frames:
            return

        for curr_frame in frames:
            if curr_start is None:
                curr_start = curr_frame
                last_frame = curr_frame
                curr_count += 1
                continue
            if curr_stride is None:
                curr_stride = abs(curr_frame - curr_start)
                curr_strides = {curr_stride}
            assert last_frame is not None
            new_stride = abs(curr_frame - last_frame)

            # Handle decimal strides and frame rounding
            # Check whether stride difference could be caused by rounding
            max_stride_delta: decimal.Decimal
            if len(curr_strides) == 1:
                stride_delta = abs(curr_stride - new_stride)
                exponent = int(stride_delta.as_tuple().exponent)
                max_stride_delta = decimal.Decimal(1).scaleb(exponent)
                if stride_delta <= max_stride_delta:
                    curr_strides.add(new_stride)

            if new_stride in curr_strides:
                # Find minimum frame value that rounds to current
                min_frame = (curr_frame - max_stride_delta / 2)  # type: ignore[possibly-undefined]
                while min_frame.quantize(curr_frame) != curr_frame:
                    min_frame = min_frame.next_plus()

                # Find maximum frame value that rounds to current
                max_frame = (curr_frame + max_stride_delta / 2)
                while max_frame.quantize(curr_frame) != curr_frame:
                    max_frame = max_frame.next_minus()

                # Adjust min stride limit until frame rounds to current
                while True:
                    new_min_stride = (min_frame - curr_start) / curr_count
                    test_frame = curr_start + new_min_stride * curr_count
                    if test_frame.quantize(curr_frame) == curr_frame:
                        break
                    min_frame = min_frame.next_plus()

                # Adjust max stride limit until frame rounds to current
                while True:
                    new_max_stride = (max_frame - curr_start) / curr_count
                    test_frame = curr_start + new_max_stride * curr_count
                    if test_frame.quantize(curr_frame) == curr_frame:
                        break
                    max_frame = max_frame.next_minus()

                # Update minimum and maximum stride values for overall range
                if curr_min_stride is not None:
                    new_min_stride = max(curr_min_stride, new_min_stride)
                if curr_max_stride is not None:
                    new_max_stride = min(curr_max_stride, new_max_stride)

                # A stride exists that rounds all frame values correctly
                if new_min_stride <= new_max_stride:
                    new_stride = curr_stride
                    curr_min_stride = new_min_stride
                    curr_max_stride = new_max_stride

            if curr_stride == new_stride:
                curr_count += 1
            elif curr_count == 2 and curr_stride != 1:
                yield _build(curr_start, curr_start, None, zfill)
                curr_start = last_frame
                curr_stride = new_stride
                curr_strides = {new_stride}
                curr_min_stride = None
                curr_max_stride = None
            else:
                stride = curr_strides.pop() if len(curr_strides) == 1 else None
                assert curr_start is not None
                if curr_stride is None:
                    yield _build(curr_start, curr_frame, curr_stride, zfill)
                else:
                    assert curr_min_stride is not None
                    assert curr_max_stride is not None
                    yield _build_decimal(curr_start, last_frame, curr_count,
                                         stride, curr_min_stride, curr_max_stride, zfill)
                curr_stride = None
                curr_strides = set()
                curr_min_stride = None
                curr_max_stride = None
                curr_start = curr_frame
                curr_count = 1

            last_frame = curr_frame

        if curr_count == 2 and curr_stride != 1:
            yield _build(curr_start, curr_start, None, zfill)
            yield _build(curr_frame, curr_frame, None, zfill)
        else:
            stride = curr_strides.pop() if len(curr_strides) == 1 else None
            assert curr_start is not None
            if curr_stride is None:
                yield _build(curr_start, curr_frame, curr_stride, zfill)
            else:
                assert curr_min_stride is not None
                assert curr_max_stride is not None
                yield _build_decimal(curr_start, curr_frame, curr_count,
                                     stride, curr_min_stride, curr_max_stride, zfill)

    @staticmethod
    def framesToFrameRanges(
            frames: typing.Iterable[int | float | decimal.Decimal | str],
            zfill: int = 0
        ) -> typing.Iterator[str]:
        """
        Converts a sequence of frames to a series of padded
        frame range strings.

        Args:
            frames (collections.Iterable): sequence of frames to process
            zfill (int): width for zero padding

        Yields:
            str:
        """
        # Ensure all frame values are of same type
        frames = normalizeFrames(frames)

        # Dispatch to appropriate specialized method based on frame type
        # Handle empty frames by defaulting to float method
        if frames and isinstance(frames[0], decimal.Decimal):
            yield from FrameSet._framesToFrameRangesDecimal(frames, zfill)  # type: ignore[arg-type]
        else:
            yield from FrameSet._framesToFrameRangesFloat(frames, zfill)  # type: ignore[arg-type]

    @staticmethod
    def framesToFrameRange(
            frames: typing.Iterable[int | float | decimal.Decimal | str],
            sort: bool = True,
            zfill: int = 0,
            compress: bool = False
        ) -> str:
        """
        Converts an iterator of frames into a
        frame range string.

        Args:
            frames (collections.Iterable): sequence of frames to process
            sort (bool): sort the sequence before processing
            zfill (int): width for zero padding
            compress (bool): remove any duplicates before processing

        Returns:
            str:
        """
        if compress:
            frames = unique(set(), frames)
        frames = list(frames)
        if not frames:
            return ''
        if len(frames) == 1:
            return pad(frames[0], zfill)
        if sort:
            frames.sort()
        ret = ','.join(FrameSet.framesToFrameRanges(frames, zfill))
        return str(ret)
