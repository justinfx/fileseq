"""
frameset - A set-like object representing a frame range for fileseq.
"""
from __future__ import annotations

import decimal
import numbers
import re
import typing
from collections.abc import Set, Sized, Iterable
from typing import Union

from . import constants  # constants.MAX_FRAME_SIZE updated during tests
from .constants import PAD_MAP, FRANGE_RE, PAD_RE
from .exceptions import MaxSizeException, ParseException
from .utils import (asString, xfrange, unique, pad, quantize,
                    normalizeFrame, normalizeFrames, batchIterable)


class FrameSet(Set):  # type:ignore[type-arg]
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

    __slots__ = ('_frange', '_items', '_order')

    _items: frozenset[int]
    _order: tuple[int, ...]

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

    def __init__(self, frange: typing.Any) -> None:
        """Initialize the :class:`FrameSet` object.
        """

        def catch_parse_err(fn, *a, **kw):  # type: ignore
            try:
                return fn(*a, **kw)
            except (TypeError, ValueError) as e:
                raise ParseException('FrameSet args parsing error: {}'.format(e)) from e

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
                self._items = frozenset(catch_parse_err(normalizeFrames, frange))  # type: ignore
                self._order = tuple(sorted(self._items))
                self._frange = catch_parse_err(  # type: ignore
                    self.framesToFrameRange, self._order, sort=False, compress=False)
                return
            # if it's ordered, find unique and build
            elif isinstance(frange, Sized) and isinstance(frange, Iterable):
                self._maxSizeCheck(frange)
                items: typing.Set[int] = set()
                order = unique(items, catch_parse_err(normalizeFrames, frange))  # type: ignore
                self._order = tuple(order)
                self._items = frozenset(items)
                self._frange = catch_parse_err(  # type: ignore
                    self.framesToFrameRange, self._order, sort=False, compress=False)
                return
            # if it's an individual number build directly
            elif isinstance(frange, (int, float, decimal.Decimal)):
                frame = normalizeFrame(frange)
                self._order = (frame,)  # type: ignore
                self._items = frozenset([frame])  # type: ignore
                self._frange = catch_parse_err(  # type: ignore
                    self.framesToFrameRange, self._order, sort=False, compress=False)
            # in all other cases, cast to a string
            else:
                try:
                    frange = asString(frange)
                except Exception as err:
                    msg = 'Could not parse "{0}": cast to string raised: {1}'
                    raise ParseException(msg.format(frange, err))

        # we're willing to trim padding characters from consideration
        # this translation is orders of magnitude faster than prior method
        frange = str(frange)
        for key in self.PAD_MAP:
            frange = frange.replace(key, '')
        self._frange = asString(frange)

        # because we're acting like a set, we need to support the empty set
        if not self._frange:
            self._items = frozenset()
            self._order = tuple()
            return

        # build the mutable stores, then cast to immutable for storage
        items = set()
        order_f: typing.List[int] = []

        maxSize = constants.MAX_FRAME_SIZE

        frange_parts: typing.List[typing.Any] = []
        frange_types: typing.List[typing.Any] = []
        for part in self._frange.split(","):
            # this is to deal with leading / trailing commas
            if not part:
                continue
            # parse the partial range
            start, end, modifier, chunk = self._parse_frange_part(part)
            frange_parts.append((start, end, modifier, chunk))
            frange_types.extend(map(type, (start, end, chunk)))

        # Determine best type for numbers in range. Note that
        # _parse_frange_part will always return decimal.Decimal for subframes
        FrameType = int
        if decimal.Decimal in frange_types:
            FrameType = decimal.Decimal  # type: ignore

        for start, end, modifier, chunk in frange_parts:
            # handle batched frames (1-100x5)
            if modifier == 'x':
                frames = xfrange(start, end, chunk, maxSize=maxSize)
                frames = [FrameType(f) for f in frames if f not in items]  # type: ignore
                self._maxSizeCheck(len(frames) + len(items))  # type: ignore
                order_f.extend(frames)
                items.update(frames)
            # handle staggered frames (1-100:5)
            elif modifier == ':':
                if '.' in str(chunk):
                    raise ValueError("Unable to stagger subframes")
                for stagger in range(chunk, 0, -1):
                    frames = xfrange(start, end, stagger, maxSize=maxSize)
                    frames = [f for f in frames if f not in items]  # type: ignore
                    self._maxSizeCheck(len(frames) + len(items))  # type: ignore
                    order_f.extend(frames)
                    items.update(frames)
            # handle filled frames (1-100y5)
            elif modifier == 'y':
                if '.' in str(chunk):
                    raise ValueError("Unable to fill subframes")
                not_good = frozenset(xfrange(start, end, chunk, maxSize=maxSize))
                frames = xfrange(start, end, 1, maxSize=maxSize)
                frames = (f for f in frames if f not in not_good)
                frames = [f for f in frames if f not in items]  # type: ignore
                self._maxSizeCheck(len(frames) + len(items))  # type: ignore
                order_f.extend(frames)
                items.update(frames)
            # handle full ranges and single frames
            else:
                frames = xfrange(start, end, 1 if start < end else -1, maxSize=maxSize)
                frames = [FrameType(f) for f in frames if f not in items]  # type: ignore
                self._maxSizeCheck(len(frames) + len(items))  # type: ignore
                order_f.extend(frames)
                items.update(frames)

        # lock the results into immutable internals
        # this allows for hashing and fast equality checking
        self._items = frozenset(items)
        self._order = tuple(order_f)

    @property
    def is_null(self) -> bool:
        """
        Read-only access to determine if the :class:`FrameSet` is the null or
        empty :class:`FrameSet`.

        Returns:
            bool:
        """
        return not (self._frange and self._items and self._order)

    @property
    def frange(self) -> str:
        """
        Read-only access to the frame range used to create this :class:`FrameSet`.

        Returns:
            str:
        """
        return self._frange or ''

    @property
    def items(self) -> frozenset[int]:
        """
        Read-only access to the unique frames that form this :class:`FrameSet`.

        Returns:
            frozenset:
        """
        return self._items

    @property
    def order(self) -> tuple[int, ...]:
        """
        Read-only access to the ordered frames that form this :class:`FrameSet`.

        Returns:
            tuple:
        """
        return self._order

    @classmethod
    def from_iterable(cls, frames: typing.Iterable[int], sort: bool = False) -> FrameSet:
        """
        Build a :class:`FrameSet` from an iterable of frames.

        Args:
            frames (collections.Iterable): an iterable object containing frames as integers
            sort (bool): True to sort frames before creation, default is False

        Returns:
            :class:`FrameSet`:
        """
        return FrameSet(sorted(frames) if sort else frames)

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
            start, end = normalizeFrames([start, end])  # type:ignore[assignment]
            range_str = "{0}-{1}".format(start, end)
        else:
            start, end = normalizeFrames([start, end])  # type:ignore[assignment]
            step = normalizeFrame(step)  # type: ignore
            range_str = "{0}-{1}x{2}".format(start, end, step)

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
            return NotImplemented

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
        return self.order.index(frame)

    def frame(self, index: int) -> int:
        """
        Return the frame at the given index.

        Args:
            index (int): the index to find the frame for

        Returns:
            int:

        Raises:
            :class:`IndexError`: if index is out of bounds
        """
        return self.order[index]

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
        return any(
            isinstance(item, (float, decimal.Decimal)) for item in self.items
        )

    def start(self) -> int:
        """
        The first frame in the :class:`FrameSet`.

        Returns:
            int:

        Raises:
            :class:`IndexError`: (with the empty :class:`FrameSet`)
        """
        return self.order[0]

    def end(self) -> int:
        """
        The last frame in the :class:`FrameSet`.

        Returns:
            int:

        Raises:
            :class:`IndexError`: (with the empty :class:`FrameSet`)
        """
        return self.order[-1]

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
        return len(self) == abs(self.end() - self.start()) + 1

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
        for frame in self.items:
            if not isinstance(frame, (int,)):
                return ''

        result: list[int] = []
        frames = sorted(self.items)
        for idx, frame in enumerate(frames[:-1]):
            next_frame = frames[idx + 1]
            if next_frame - frame != 1:
                r = range(frame + 1, next_frame)
                # Check if the next update to the result set
                # will exceed out max frame size.
                # Prevent memory overflows.
                self._maxSizeCheck(len(r) + len(result))
                result += r

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
        return FrameSet(FrameSet.framesToFrameRange(
            self.items, sort=True, compress=False))

    def batches(self, batch_size: int, frames: bool = False) -> typing.Iterator[typing.Any]:
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
            return batch_it  # type: ignore

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
            if '__frange' in state and '__set' in state and '__list' in state:
                self._frange = state['__frange']
                self._items = frozenset(state['__set'])
                self._order = tuple(state['__list'])
            else:
                for k in self.__slots__:
                    setattr(self, k, state[k])
        else:
            msg = "Unrecognized state data from which to deserialize FrameSet"
            raise ValueError(msg)

    def __getitem__(self, index: int) -> int:
        """
        Allows indexing into the ordered frames of this :class:`FrameSet`.

        Args:
            index (int): the index to retrieve

        Returns:
            int:

        Raises:
            :class:`IndexError`: if index is out of bounds
        """
        return self.order[index]

    def __len__(self) -> int:
        """
        Returns the length of the ordered frames of this :class:`FrameSet`.

        Returns:
            int:
        """
        return len(self.order)

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

    def __iter__(self):  # type: ignore
        """
        Allows for iteration over the ordered frames of this :class:`FrameSet`.

        Returns:
            generator:
        """
        return (i for i in self.order)

    def __reversed__(self):  # type: ignore
        """
        Allows for reversed iteration over the ordered frames of this
        :class:`FrameSet`.

        Returns:
            generator:
        """
        return (i for i in reversed(self.order))

    def __contains__(self, item: typing.Any) -> bool:
        """
        Check if item is a member of this :class:`FrameSet`.

        Args:
            item (int): the frame number to check for

        Returns:
            bool:
        """
        return item in self.items

    def __hash__(self) -> int:
        """
        Builds the hash of this :class:`FrameSet` for equality checking and to
        allow use as a dictionary key.

        Returns:
            int:
        """
        return hash(self.frange) | hash(self.items) | hash(self.order)

    def __lt__(self, other: typing.Any) -> typing.Any:
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
        return self.items < other.items or (
                self.items == other.items and self.order < other.order)

    def __le__(self, other: typing.Any) -> typing.Any:
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
        return self.items <= other.items

    def __eq__(self, other: typing.Any) -> typing.Any:
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
            if not hasattr(other, '__iter__'):
                return NotImplemented
            other = self.from_iterable(other)
        this = hash(self.items) | hash(self.order)
        that = hash(other.items) | hash(other.order)
        return this == that

    def __ne__(self, other: typing.Any) -> typing.Any:
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

    def __ge__(self, other: typing.Any) -> typing.Any:
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
        return self.items >= other.items

    def __gt__(self, other: typing.Any) -> typing.Any:
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
        return self.items > other.items or (
                self.items == other.items and self.order > other.order)

    def __and__(self, other: typing.Any) -> typing.Any:
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
        return self.from_iterable(self.items & other.items, sort=True)

    __rand__ = __and__

    def __sub__(self, other: typing.Any) -> typing.Any:
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
        return self.from_iterable(self.items - other.items, sort=True)

    def __rsub__(self, other: typing.Any) -> typing.Any:
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
        return self.from_iterable(other.items - self.items, sort=True)

    def __or__(self, other: typing.Any) -> typing.Any:
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
        return self.from_iterable(self.items | other.items, sort=True)

    __ror__ = __or__

    def __xor__(self, other: typing.Any) -> typing.Any:
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
        return self.from_iterable(self.items ^ other.items, sort=True)

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
            return NotImplemented
        return self.items.isdisjoint(other.items)

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
            return NotImplemented
        return self.items <= other.items  # type: ignore

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
            return NotImplemented
        return self.items >= other.items  # type: ignore

    def union(self, *other: typing.Any) -> FrameSet:
        """
        Returns a new :class:`FrameSet` with the elements of `self` and
        of `other`.

        Args:
            other (:class:`FrameSet`): or objects that can cast to :class:`FrameSet`

        Returns:
            :class:`FrameSet`:
        """
        from_frozenset = self.items.union(*(set(o) for o in other))
        return self.from_iterable(from_frozenset, sort=True)

    def intersection(self, *other: typing.Any) -> FrameSet:
        """
        Returns a new :class:`FrameSet` with the elements common to `self` and
        `other`.

        Args:
            other (:class:`FrameSet`): or objects that can cast to :class:`FrameSet`

        Returns:
            :class:`FrameSet`:
        """
        from_frozenset = self.items.intersection(*(set(o) for o in other))
        return self.from_iterable(from_frozenset, sort=True)

    def difference(self, *other: typing.Any) -> FrameSet:
        """
        Returns a new :class:`FrameSet` with elements in `self` but not in
        `other`.

        Args:
            other (:class:`FrameSet`): or objects that can cast to :class:`FrameSet`

        Returns:
            :class:`FrameSet`:
        """
        from_frozenset = self.items.difference(*(set(o) for o in other))
        return self.from_iterable(from_frozenset, sort=True)

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
            return NotImplemented
        from_frozenset = self.items.symmetric_difference(other.items)
        return self.from_iterable(from_frozenset, sort=True)

    def copy(self) -> FrameSet:
        """
        Create a deep copy of this :class:`FrameSet`.

        Returns:
            :class:`.FrameSet`:
        """
        fs = self.__class__.__new__(self.__class__)
        fs._frange = self._frange
        fs._items = self._items
        fs._order = self._order
        return fs

    @classmethod
    def _maxSizeCheck(cls, obj: int | float | decimal.Decimal | Sized) -> None:
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
    def _build_frange_part(start: object, stop: object, stride: int|float|decimal.Decimal|None, zfill: int = 0) -> str:
        """
        Private method: builds a proper and padded frame range string.

        Args:
            start (int): first frame
            stop (int or None): last frame
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
    def framesToFrameRanges(
            frames: typing.Iterable[typing.Any],
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
        _build = FrameSet._build_frange_part
        _build_decimal = FrameSet._build_frange_part_decimal

        # Ensure all frame values are of same type
        frames = normalizeFrames(frames)

        curr_start = None
        curr_stride = None
        curr_strides = None  # used for decimal frame handling only
        curr_min_stride = None  # used for decimal frame handling only
        curr_max_stride = None  # used for decimal frame handling only
        curr_frame = None
        last_frame = None
        curr_count = 0
        for curr_frame in frames:
            if curr_start is None:
                curr_start = curr_frame
                last_frame = curr_frame
                curr_count += 1
                continue
            if curr_stride is None:
                curr_stride = abs(curr_frame - curr_start)
                curr_strides = {curr_stride}
            new_stride = abs(curr_frame - last_frame)

            # Handle decimal strides and frame rounding
            if isinstance(curr_stride, decimal.Decimal):
                # Check whether stride difference could be caused by rounding
                if len(curr_strides) == 1:
                    stride_delta = abs(curr_stride - new_stride)
                    exponent = stride_delta.as_tuple().exponent
                    max_stride_delta = decimal.Decimal(1).scaleb(exponent)
                    if stride_delta <= max_stride_delta:
                        curr_strides.add(new_stride)

                if new_stride in curr_strides:
                    # Find minimum frame value that rounds to current
                    min_frame = (curr_frame - max_stride_delta / 2)
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
                if isinstance(curr_stride, decimal.Decimal):
                    stride = curr_strides.pop() if len(curr_strides) == 1 else None
                    yield _build_decimal(curr_start, last_frame, curr_count,
                                         stride, curr_min_stride, curr_max_stride, zfill)
                else:
                    yield _build(curr_start, last_frame, curr_stride, zfill)
                curr_stride = None
                curr_strides = None
                curr_min_stride = None
                curr_max_stride = None
                curr_start = curr_frame
                curr_count = 1

            last_frame = curr_frame

        if curr_count == 2 and curr_stride != 1:
            yield _build(curr_start, curr_start, None, zfill)
            yield _build(curr_frame, curr_frame, None, zfill)
        else:
            if isinstance(curr_stride, decimal.Decimal):
                stride = curr_strides.pop() if len(curr_strides) == 1 else None
                yield _build_decimal(curr_start, curr_frame, curr_count,
                                     stride, curr_min_stride, curr_max_stride, zfill)
            else:
                yield _build(curr_start, curr_frame, curr_stride, zfill)

    @staticmethod
    def framesToFrameRange(
            frames: typing.Iterable[typing.Any],
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
