#! /usr/bin/env python
"""
frameset - A set-like object representing a frame range for fileseq.
"""

import numbers

from collections import Set, Sequence

from fileseq import constants
from fileseq.constants import PAD_MAP, FRANGE_RE, PAD_RE
from fileseq.exceptions import MaxSizeException, ParseException
from fileseq.utils import xfrange, unique, pad

# Issue #44
# Possibly use an alternate xrange implementation, depending on platform. 
from fileseq.utils import xrange

class FrameSet(Set):
    """
    A :class:`FrameSet` is an immutable representation of the ordered, unique
    set of frames in a given frame range.

    The frame range can be expressed in the following ways:
        - 1-5
        - 1-5,10-20
        - 1-100x5 (every fifth frame)
        - 1-100y5 (opposite of above, fills in missing frames)
        - 1-100:4 (same as 1-100x4,1-100x3,1-100x2,1-100)

    A :class:`FrameSet` is effectively an ordered frozenset, with
    FrameSet-returning versions of frozenset methods:

        >>> FrameSet('1-5').union(FrameSet('5-10'))
        FrameSet('1-10')
        >>> FrameSet('1-5').intersection(FrameSet('5-10'))
        FrameSet('5')

    Because a FrameSet is hashable, it can be used as the key to a dictionary:

        >>> {FrameSet('1-20'): 'good'}

    Caveats:
        1. Because the internal storage of a ``FrameSet`` contains the discreet
           values of the entire range, an exception will be thrown if the range
           exceeds a large reasonable limit, which could lead to huge memory 
           allocations or memory failures. See `fileseq.constants.MAX_FRAME_SIZE`.
        2. All frozenset operations return a normalized :class:`FrameSet`:
           internal frames are in numerically increasing order.
        3. Equality is based on the contents and order, NOT the frame range
           string (there are a finite, but potentially
           extremely large, number of strings that can represent any given range,
           only a "best guess" can be made).
        4. Human-created frame ranges (ie 1-100x5) will be reduced to the
           actual internal frames (ie 1-96x5).
        5. The "null" :class:`Frameset` (``FrameSet('')``) is now a valid thing
           to create, it is required by set operations, but may cause confusion
           as both its start and end methods will raise IndexError.  The
           :meth:`is_null`
           property has been added to allow you to guard against this.

    :type frange: str
    :param frange: the frame range as a string (ie "1-100x5")
    :rtype: None
    :raises: :class:`fileseq.exceptions.ParseException` if the frame range
             (or a portion of it) could not be parsed.
             :class:`fileseq.exceptions.MaxSizeException` if the range exceeds
             `fileseq.constants.MAX_FRAME_SIZE`
    """

    __slots__ = ('_frange', '_items', '_order')

    def __new__(cls, *args, **kwargs):
        """
        Initialize the :class:`FrameSet` object.

        :type frange: str
        :param frange: the frame range as a string (ie "1-100x5")
        :returns: the :class:`FrameSet` instance
        :raises: :class:`fileseq.exceptions.ParseException` if the frame range
                 (or a portion of it) could not be parsed
        """
        self = super(cls, FrameSet).__new__(cls, *args, **kwargs)
        return self


    def __init__(self, frange):        
        # if the user provides anything but a string, short-circuit the build
        if not isinstance(frange, basestring):
            # if it's apparently a FrameSet already, short-circuit the build
            if set(dir(frange)).issuperset(self.__slots__):
                for attr in self.__slots__:
                    setattr(self, attr, getattr(frange, attr))
                return
            # if it's inherently disordered, sort and build
            elif isinstance(frange, Set):
                self._maxSizeCheck(frange)
                self._items = frozenset(map(int, frange))
                self._order = tuple(sorted(self._items))
                self._frange = FrameSet.framesToFrameRange(
                    self._order, sort=False, compress=False)
                return
            # if it's ordered, find unique and build
            elif isinstance(frange, Sequence):
                self._maxSizeCheck(frange)
                items = set()
                order = unique(items, map(int, frange))
                self._order = tuple(order)
                self._items = frozenset(items)
                self._frange = FrameSet.framesToFrameRange(
                    self._order, sort=False, compress=False)
                return
            # in all other cases, cast to a string
            else:
                try:
                    frange = str(frange)
                except Exception as err:
                    msg = 'Could not parse "{0}": cast to string raised: {1}'
                    raise ParseException(msg.format(frange, err))

        # we're willing to trim padding characters from consideration
        # this translation is orders of magnitude faster than prior method
        self._frange = str(frange).translate(None, ''.join(PAD_MAP.keys()))

        # because we're acting like a set, we need to support the empty set
        if not self._frange:
            self._items = frozenset()
            self._order = tuple()
            return

        # build the mutable stores, then cast to immutable for storage
        items = set()
        order = []

        maxSize = constants.MAX_FRAME_SIZE 

        for part in self._frange.split(","):
            # this is to deal with leading / trailing commas
            if not part:
                continue
            # parse the partial range
            start, end, modifier, chunk = FrameSet._parse_frange_part(part)
            # handle batched frames (1-100x5)
            if modifier == 'x':
                frames = xfrange(start, end, chunk, maxSize=maxSize)
                frames = [f for f in frames if f not in items]
                self._maxSizeCheck(len(frames) + len(items))
                order.extend(frames)
                items.update(frames)
            # handle staggered frames (1-100:5)
            elif modifier == ':':
                for stagger in xrange(chunk, 0, -1):
                    frames = xfrange(start, end, stagger, maxSize=maxSize)
                    frames = [f for f in frames if f not in items]
                    self._maxSizeCheck(len(frames) + len(items))
                    order.extend(frames)
                    items.update(frames)
            # handle filled frames (1-100y5)
            elif modifier == 'y':
                not_good = frozenset(xfrange(start, end, chunk, maxSize=maxSize))
                frames = xfrange(start, end, 1, maxSize=maxSize)
                frames = (f for f in frames if f not in not_good)
                frames = [f for f in frames if f not in items]
                self._maxSizeCheck(len(frames) + len(items))
                order.extend(frames)
                items.update(frames)
            # handle full ranges and single frames
            else:
                frames = xfrange(start, end, 1 if start < end else -1, maxSize=maxSize)
                frames = [f for f in frames if f not in items]
                self._maxSizeCheck(len(frames) + len(items))
                order.extend(frames)
                items.update(frames)

        # lock the results into immutable internals
        # this allows for hashing and fast equality checking
        self._items = frozenset(items)
        self._order = tuple(order)

    @property
    def is_null(self):
        """
        Read-only access to determine if the :class:`FrameSet` is the null or
        empty :class:`FrameSet`.

        :rtype: bool
        """
        return not (self._frange and self._items and self._order)

    @property
    def frange(self):
        """
        Read-only access to the frame range used to create this :class:`FrameSet`.

        :rtype: frozenset
        """
        return self._frange

    @property
    def items(self):
        """
        Read-only access to the unique frames that form this :class:`FrameSet`.

        :rtype: frozenset
        """
        return self._items

    @property
    def order(self):
        """
        Read-only access to the ordered frames that form this :class:`FrameSet`.

        :rtype: tuple
        """
        return self._order

    @classmethod
    def from_iterable(cls, frames, sort=False):
        """
        Build a :class:`FrameSet` from an iterable of frames.

        :param frames: an iterable object containing frames as integers
        :param sort: True to sort frames before creation, default is False
        :rtype: :class:`FrameSet`
        """
        return FrameSet(sorted(frames) if sort else frames)

    @classmethod
    def _cast_to_frameset(cls, other):
        """
        Private method to simplify comparison operations.

        :param other: the :class:`FrameSet`, set, frozenset, or iterable to be compared
        :rtype: :class:`FrameSet`
        :returns: :class:`NotImplemented` if a comparison is impossible
        """
        if isinstance(other, FrameSet):
            return other
        try:
            return FrameSet(other)
        except Exception:
            return NotImplemented

    def index(self, frame):
        """
        Return the index of the given frame number within the :class:`FrameSet`.

        :type frame: int
        :param frame: the frame number to find the index for
        :rtype: int
        :raises: :class:`ValueError` if frame is not in self
        """
        return self.order.index(frame)

    def frame(self, index):
        """
        Return the frame at the given index.

        :type index: int
        :param index: the index to find the frame for
        :rtype: int
        :raises: :class:`IndexError` if index is out of bounds
        """
        return self.order[index]

    def hasFrame(self, frame):
        """
        Check if the :class:`FrameSet` contains the frame.

        :type frame: int
        :param frame: the frame number to search for
        :rtype: bool
        """
        return frame in self

    def start(self):
        """
        The first frame in the :class:`FrameSet`.

        :rtype: int
        :raises: :class:`IndexError` (with the empty :class:`FrameSet`)
        """
        return self.order[0]

    def end(self):
        """
        The last frame in the :class:`FrameSet`.

        :rtype: int
        :raises: :class:`IndexError` (with the empty :class:`FrameSet`)
        """
        return self.order[-1]

    def isConsecutive(self):
        """
        Return whether the frame range represents consecutive integers,
        as opposed to having a stepping >= 2
    
        :Example:
            >>> FrameSet('1-100').isConsecutive()
            True
            >>> FrameSet('1-100x2').isConsecutive()
            False
            >>> FrameSet('1-50,60-100').isConsecutive()
            False

        :rtype: bool
        """
        return len(self) == abs(self.end()-self.start()) + 1

    def frameRange(self, zfill=0):
        """
        Return the frame range used to create this :class:`FrameSet`, padded if
        desired.

        :Example:
            >>> FrameSet('1-100').frameRange()
            '1-100'
            >>> FrameSet('1-100').frameRange(5)
            '00001-00100'

        :type zfill: int
        :param zfill: the width to use to zero-pad the frame range string
        :rtype: str
        """
        return FrameSet.padFrameRange(self.frange, zfill)

    def invertedFrameRange(self, zfill=0):
        """
        Return the inverse of the :class:`FrameSet` 's frame range, padded if
        desired.
        The inverse is every frame within the full extent of the range.

        :Example:
            >>> FrameSet('1-100x2').invertedFrameRange()
            '2-98x2'
            >>> FrameSet('1-100x2').invertedFrameRange(5)
            '00002-00098x2'

        If the inverted frame size exceeds `fileseq.constants.MAX_FRAME_SIZE`, 
        a ``MaxSizeException`` will be raised.

        :type zfill: int
        :param zfill: the width to use to zero-pad the frame range string
        :rtype: str
        :raises: :class:`fileseq.exceptions.MaxSizeException`
        """
        result = []
        frames = sorted(self.items)
        for idx, frame in enumerate(frames[:-1]):
            next_frame = frames[idx + 1]
            if next_frame - frame != 1:
                r = xrange(frame + 1, next_frame)
                # Check if the next update to the result set
                # will exceed out max frame size. 
                # Prevent memory overflows.
                self._maxSizeCheck(len(r) + len(result))
                result += r
        
        if not result:
            return ''
        
        return FrameSet.framesToFrameRange(
            result, zfill=zfill, sort=False, compress=False)

    def normalize(self):
        """
        Returns a new normalized (sorted and compacted) :class:`FrameSet`.

        :rtype: :class:`FrameSet`
        """
        return FrameSet(FrameSet.framesToFrameRange(
            self.items, sort=True, compress=False))

    def __getstate__(self):
        """
        Allows for serialization to a pickled :class:`FrameSet`.

        :rtype: tuple (frame range string, )
        """
        # we have to special-case the empty FrameSet, because of a quirk in
        # Python where __setstate__ will not be called if the return value of
        # bool(__getstate__) == False.  A tuple with ('',) will return True.
        return (self.frange, )

    def __setstate__(self, state):
        """
        Allows for de-serialization from a pickled :class:`FrameSet`.

        :type state: tuple, str, or dict
        :param state: A string/dict can be used for backwards compatibility
        :rtype: None
        :raises: :class:`ValueError` if state is not an appropriate type
        """
        if isinstance(state, tuple):
            # this is to allow unpickling of "3rd generation" FrameSets,
            # which are immutable and may be empty.
            self.__init__(state[0])
        elif isinstance(state, basestring):
            # this is to allow unpickling of "2nd generation" FrameSets,
            # which were mutable and could not be empty.
            self.__init__(state)
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

    def __getitem__(self, index):
        """
        Allows indexing into the ordered frames of this :class:`FrameSet`.

        :type int:
        :param index: the index to retrieve
        :rtype: int
        :raises: :class:`IndexError` if index is out of bounds
        """
        return self.order[index]

    def __len__(self):
        """
        Returns the length of the ordered frames of this :class:`FrameSet`.

        :rtype: int
        """
        return len(self.order)

    def __str__(self):
        """
        Returns the frame range string of this :class:`FrameSet`.

        :rtype: str
        """
        return self.frange

    def __repr__(self):
        """
        Returns a long-form representation of this :class:`FrameSet`.

        :rtype: str
        """
        return '{0}("{1}")'.format(self.__class__.__name__, self.frange)

    def __iter__(self):
        """
        Allows for iteration over the ordered frames of this :class:`FrameSet`.

        :rtype: generator
        """
        return (i for i in self.order)

    def __reversed__(self):
        """
        Allows for reversed iteration over the ordered frames of this
        :class:`FrameSet`.

        :rtype: generator
        """
        return (i for i in reversed(self.order))

    def __contains__(self, item):
        """
        Check if item is a member of this :class:`FrameSet`.

        :type item: int
        :param item: the frame number to check for
        :rtype: bool
        """
        return item in self.items

    def __hash__(self):
        """
        Builds the hash of this :class:`FrameSet` for equality checking and to
        allow use as a dictionary key.

        :rtype: int
        """
        return hash(self.frange) | hash(self.items) | hash(self.order)

    def __lt__(self, other):
        """
        Check if self < other via a comparison of the contents. If other is not
        a :class:`FrameSet`, but is a set, frozenset, or is iterable, it will be
        cast to a :class:`FrameSet`.

        .. note::

            A :class:`FrameSet` is less than other if the set of its contents are
            less, OR if the contents are equal but the order of the items is less.

            .. code-block:: python
                :caption: Same contents, but (1,2,3,4,5) sorts below (5,4,3,2,1)

                >>> FrameSet("1-5") < FrameSet("5-1")
                True

        :type other: FrameSet
        :param other: Can also be an object that can be cast to a :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items < other.items or (
            self.items == other.items and self.order < other.order)

    def __le__(self, other):
        """
        Check if `self` <= `other` via a comparison of the contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        :type other: FrameSet
        :param other: Also accepts an object that can be cast to a :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items <= other.items

    def __eq__(self, other):
        """
        Check if `self` == `other` via a comparison of the hash of
        their contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        :type other: :class:`FrameSet`
        :param other: Also accepts an object that can be cast to a :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        if not isinstance(other, FrameSet):
            if not hasattr(other, '__iter__'):
                return NotImplemented
            other = self.from_iterable(other)
        this = hash(self.items) | hash(self.order)
        that = hash(other.items) | hash(other.order)
        return this == that

    def __ne__(self, other):
        """
        Check if `self` != `other` via a comparison of the hash of
        their contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        :type other: :class:`FrameSet`
        :param other: Also accepts an object that can be cast to a :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        is_equals = self == other
        if is_equals != NotImplemented:
            return not is_equals
        return is_equals

    def __ge__(self, other):
        """
        Check if `self` >= `other` via a comparison of the contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        :type other: :class:`FrameSet`
        :param other: Also accepts an object that can be cast to one a :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items >= other.items

    def __gt__(self, other):
        """
        Check if `self` > `other` via a comparison of the contents.
        If `other` is not a :class:`FrameSet`, but is a set, frozenset, or
        is iterable, it will be cast to a :class:`FrameSet`.

        .. note::
           A :class:`FrameSet` is greater than `other` if the set of its
           contents are greater,
           OR if the contents are equal but the order is greater.

           .. code-block:: python
               :caption: Same contents, but (1,2,3,4,5) sorts below (5,4,3,2,1)

               >>> FrameSet("1-5") > FrameSet("5-1")
               False

        :type other: :class:`FrameSet`
        :param other: Also accepts an object that can be cast to a :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if :param: other fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items > other.items or (
            self.items == other.items and self.order > other.order)

    def __and__(self, other):
        """
        Overloads the ``&`` operator.
        Returns a new :class:`FrameSet` that holds only the
        frames `self` and `other` have in common.

        .. note::

            The order of operations is irrelevant:
            ``(self & other) == (other & self)``

        :type other: :class:`FrameSet`
        :rtype: :class:`FrameSet`, or :class:`NotImplemented` if :param: other
                fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.from_iterable(self.items & other.items, sort=True)

    __rand__ = __and__

    def __sub__(self, other):
        """
        Overloads the ``-`` operator.
        Returns a new :class:`FrameSet` that holds only the
        frames of `self` that are not in `other.`

        .. note::

            This is for left-hand subtraction (``self - other``).

        :type other: :class:`FrameSet`
        :rtype: :class:`FrameSet`, or :class:`NotImplemented` if `other`
                fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.from_iterable(self.items - other.items, sort=True)

    def __rsub__(self, other):
        """
        Overloads the ``-`` operator.
        Returns a new :class:`FrameSet` that holds only the
        frames of `other` that are not in `self.`

        .. note::

            This is for right-hand subtraction (``other - self``).

        :type other: :class:`FrameSet`
        :rtype: :class:`FrameSet`, or :class:`NotImplemented` if `other`
                fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.from_iterable(other.items - self.items, sort=True)

    def __or__(self, other):
        """
        Overloads the ``|`` operator.
        Returns a new :class:`FrameSet` that holds all the
        frames in `self,` `other,` or both.

        .. note::

            The order of operations is irrelevant:
            ``(self | other) == (other | self)``

        :type other: :class:`FrameSet`
        :rtype: :class:`FrameSet`, or :class:`NotImplemented` if `other`
                fails to convert to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.from_iterable(self.items | other.items, sort=True)

    __ror__ = __or__

    def __xor__(self, other):
        """
        Overloads the ``^`` operator.
        Returns a new :class:`FrameSet` that holds all the
        frames in `self` or `other` but not both.

        .. note::
            The order of operations is irrelevant:
            ``(self ^ other) == (other ^ self)``

        :type other: :class:`FrameSet`
        :rtype: :class:`FrameSet`, or :class:`NotImplemented` if `other`
                fails to convert to a :class:`FrameSet`.
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.from_iterable(self.items ^ other.items, sort=True)

    __rxor__ = __xor__

    def isdisjoint(self, other):
        """
        Check if the contents of :class:self has no common intersection with the
        contents of :class:other.

        :type other: :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items.isdisjoint(other.items)

    def issubset(self, other):
        """
        Check if the contents of `self` is a subset of the contents of
        `other.`

        :type other: :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items <= other.items

    def issuperset(self, other):
        """
        Check if the contents of `self` is a superset of the contents of
        `other.`

        :type other: :class:`FrameSet`
        :rtype: bool, or :class:`NotImplemented` if `other` fails to convert
                to a :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        return self.items >= other.items

    def union(self, *other):
        """
        Returns a new :class:`FrameSet` with the elements of `self` and
        of `other`.

        :type other: :class:`FrameSet` or objects that can cast to :class:`FrameSet`
        :rtype: :class:`FrameSet`
        """
        from_frozenset = self.items.union(*map(set, other))
        return self.from_iterable(from_frozenset, sort=True)

    def intersection(self, *other):
        """
        Returns a new :class:`FrameSet` with the elements common to `self` and
        `other`.

        :type other: :class:`FrameSet` or objects that can cast to :class:`FrameSet`
        :rtype: :class:`FrameSet`
        """
        from_frozenset = self.items.intersection(*map(set, other))
        return self.from_iterable(from_frozenset, sort=True)

    def difference(self, *other):
        """
        Returns a new :class:`FrameSet` with elements in `self` but not in
        `other`.

        :type other: :class:`FrameSet` or objects that can cast to :class:`FrameSet`
        :rtype: :class:`FrameSet`
        """
        from_frozenset = self.items.difference(*map(set, other))
        return self.from_iterable(from_frozenset, sort=True)

    def symmetric_difference(self, other):
        """
        Returns a new :class:`FrameSet` that contains all the elements in either
        `self` or `other`, but not both.

        :type other: :class:`FrameSet`
        :rtype: :class:`FrameSet`
        """
        other = self._cast_to_frameset(other)
        if other is NotImplemented:
            return NotImplemented
        from_frozenset = self.items.symmetric_difference(other.items)
        return self.from_iterable(from_frozenset, sort=True)

    def copy(self):
        """
        Returns a shallow copy of this :class:`FrameSet`.

        :rtype: :class:`FrameSet`
        """
        return FrameSet(str(self))

    @classmethod
    def _maxSizeCheck(cls, obj):
        """
        Raise a MaxSizeException if ``obj`` exceeds MAX_FRAME_SIZE

        :type obj: number or collection
        :raises: :class:`fileseq.exceptions.MaxSizeException`
        """
        fail = False
        size = 0

        if isinstance(obj, numbers.Number):
            if obj > constants.MAX_FRAME_SIZE:
                fail = True
                size = obj

        elif hasattr(obj, '__len__'):
            size = len(obj)
            fail = size > constants.MAX_FRAME_SIZE

        if fail:
            raise MaxSizeException('Frame size %s > %s (MAX_FRAME_SIZE)' \
                    % (size, constants.MAX_FRAME_SIZE))

    @staticmethod
    def isFrameRange(frange):
        """
        Return True if the given string is a frame range. Any padding
        characters, such as '#' and '@' are ignored.

        :type frange: str
        :param frange: a frame range to test
        :rtype: bool
        """
        # we're willing to trim padding characters from consideration
        # this translation is orders of magnitude faster than prior method
        frange = str(frange).translate(None, ''.join(PAD_MAP.keys()))
        if not frange:
            return True
        for part in frange.split(','):
            if not part:
                continue
            try:
                FrameSet._parse_frange_part(part)
            except ParseException:
                return False
        return True

    @staticmethod
    def padFrameRange(frange, zfill):
        """
        Return the zero-padded version of the frame range string.

        :type frange: str
        :param frange: a frame range to test
        :rtype: str
        """
        def _do_pad(match):
            """
            Substitutes padded for unpadded frames.
            """
            result = list(match.groups())
            result[1] = pad(result[1], zfill)
            if result[4]:
                result[4] = pad(result[4], zfill)
            return ''.join((i for i in result if i))
        return PAD_RE.sub(_do_pad, frange)

    @staticmethod
    def _parse_frange_part(frange):
        """
        Internal method: parse a discrete frame range part.

        :type frange: str
        :param frange: single part of a frame range as a string (ie "1-100x5")
        :rtype: tuple (start, end, modifier, chunk)
        :raises: :class:`fileseq.exceptions.ParseException` if the frame range
                 can not be parsed
        """
        match = FRANGE_RE.match(frange)
        if not match:
            msg = 'Could not parse "{0}": did not match {1}'
            raise ParseException(msg.format(frange, FRANGE_RE.pattern))
        start, end, modifier, chunk = match.groups()
        start = int(start)
        end = int(end) if end is not None else start
        chunk = abs(int(chunk)) if chunk is not None else 1
        # a zero chunk is just plain illogical
        if chunk == 0:
            msg = 'Could not parse "{0}": chunk cannot be 0'
            raise ParseException(msg.format(frange))
        return start, end, modifier, chunk

    @staticmethod
    def _build_frange_part(start, stop, stride, zfill=0):
        """
        Private method: builds a proper and padded
        :class:`fileseq.framerange.FrameRange` string.

        :type start: int
        :param start: first frame
        :type stop: int
        :param stop: last frame
        :type stride: int
        :param stride: increment
        :type zfill: int
        :param zfill: width for zero padding
        :rtype: str
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
            return '{0}-{1}x{2}'.format(pad_start, pad_stop, stride)

    @staticmethod
    def framesToFrameRanges(frames, zfill=0):
        """
        Converts a sequence of frames to a series of padded
        :class:`fileseq.framerange.FrameRange` s.

        :type frames: iterable
        :param frames: sequence of frames to process
        :type zfill: int
        :param zfill: width for zero padding
        :rtype: generator
        """
        _build = FrameSet._build_frange_part
        curr_start = None
        curr_stride = None
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
                curr_stride = abs(curr_frame-curr_start)
            new_stride = abs(curr_frame-last_frame)
            if curr_stride == new_stride:
                last_frame = curr_frame
                curr_count += 1
            elif curr_count == 2 and curr_stride != 1:
                yield _build(curr_start, curr_start, None, zfill)
                curr_start = last_frame
                curr_stride = new_stride
                last_frame = curr_frame
            else:
                yield _build(curr_start, last_frame, curr_stride, zfill)
                curr_stride = None
                curr_start = curr_frame
                last_frame = curr_frame
                curr_count = 1
        if curr_count == 2 and curr_stride != 1:
            yield _build(curr_start, curr_start, None, zfill)
            yield _build(curr_frame, curr_frame, None, zfill)
        else:
            yield _build(curr_start, curr_frame, curr_stride, zfill)

    @staticmethod
    def framesToFrameRange(frames, sort=True, zfill=0, compress=False):
        """
        Converts an iterator of frames into a
        :class:`fileseq.framerange.FrameRange`.

        :type frames: iterable
        :param frames: sequence of frames to process
        :type sort: bool
        :param sort: sort the sequence before processing
        :type zfill: int
        :param zfill: width for zero padding
        :type compress: bool
        :param compress: remove any duplicates before processing
        :rtype: str
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
        return ','.join(FrameSet.framesToFrameRanges(frames, zfill))
