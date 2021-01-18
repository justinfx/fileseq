#!/usr/bin/env python

from __future__ import division
from __future__ import absolute_import

from future import standard_library
standard_library.install_aliases()
from future.utils import string_types, text_type, native_str

import unittest
import pickle
import re
import types

from fileseq.utils import *
from fileseq import FrameSet, framesToFrameRange, ParseException


def _yrange(first, last=None, incr=1):
    """
    Simple value generator for the 1-20y5 syntax.
    :param first: as per xrange
    :param last: as per xrange
    :param incr: as per xrange
    :return: generator
    """
    if last is None:
        first, last = 0, first
    whole = list(range(first, last, 1 if incr >= 0 else -1))
    filt = set(whole[::abs(incr)])
    for i in whole:
        if i not in filt:
            yield i


def _srange(first, last=None, incr=1):
    """
    Simple value generator for the 1-20:5 syntax.
    :param first: as per xrange
    :param last: as per xrange
    :param incr: as per xrange
    :return: generator
    """
    if last is None:
        first, last = 0, first
    whole = list(range(first, last, 1 if incr >= 0 else -1))
    sent = set()
    for stagger in range(abs(incr), 0, -1):
        for i in whole[::stagger]:
            if i not in sent:
                sent.add(i)
                yield i


def _uchain(*args):
    """
    As per itertools.chain, but will only yield items not previously yielded.
    :param args: one or more iterables to chain
    :return: generator
    """
    sent = set()
    for i in chain(*args):
        if i not in sent:
            yield i
            sent.add(i)


FRAME_SET_SHOULD_SUCCEED = [
    # the null value
    ("Empty", '', []),
    # individual frames
    ('Zero', '0', [0]),
    ('NegZero', '-0', [0]),
    ('Pos', '1', [1]),
    ('Neg', '-1', [-1]),
    # permutations on comma separated individual frames
    ('DupePos', '1,1,1', [1]),
    ('DupeNeg', '-1,-1,-1', [-1]),
    ('DupeMix', '-1,1,-1,1', [-1,1]),
    ('CommaSepPos', '1,3,17', [1,3,17]),
    ('CommaSepNeg', '-1,-3,-17', [-1,-3,-17]),
    ('CommaSepMix', '1,-3,17', [1,-3,17]),
    ('CommaSepPosInv', '17,3,1', [17,3,1]),
    ('CommaSepNegInv', '-17,-3,-1', [-17,-3,-1]),
    ('CommaSepMixInv', '17,-3,1', [17,-3,1]),
    ('CommaSepMixInv', '17,-3,1', [17,-3,1]),
    ("CommaTrailing", "1,", [1]),
    ("CommaLeading", ",1", [1]),
    ("CommaDupes", "1,,,,,,2,,,,,3,,,", [1,2,3]),
    # args that str(arg) cast to a valid FrameSet
    ('PosInt', 1, [1]),
    ('NegInt', -1, [-1]),
    ('FrameSet', FrameSet("1-20"), list(range(1,21))),
    # unicode args that are the equivalent of a valid FrameSet
    ('UnicodeEquivalentRange', u'-1--20', list(range(-1,-21,-1))),
    ('UnicodeEquivalentRangeChunk', u'-1--20x5', list(range(-1,-21,-5))),
    ('UnicodeEquivalentRangeFill', u'-1--20y5', list(_yrange(-1,-21,-5))),
    ('UnicodeEquivalentRangeStagger', u'-1--20:5', list(_srange(-1,-21,-5))),
]

LO_RANGES = [
    # low value permutations of signed integer ranges, these will all be individually tested
    ('PosToPos', '1-20', list(range(1,21,1))),
    ('NegToPos', '-1-20', list(range(-1,21,1))),
    ('NegToNeg', '-1--20', list(range(-1,-21,-1))),
    ('PosToNeg', '1--20', list(range(1,-21,-1))),
    ('PosToPosInv', '20-1', list(range(20,0,-1))),
    ('NegToPosInv', '-20-1', list(range(-20,2,1))),
    ('NegToNegInv', '-20--1', list(range(-20,0,1))),
    ('PosToNegInv', '20--1', list(range(20,-2,-1))),
    ('PosToPosChunk', '1-20x5', list(range(1,21,5))),
    ('NegToPosChunk', '-1-20x5', list(range(-1,21,5))),
    ('NegToNegChunk', '-1--20x5', list(range(-1,-21,-5))),
    ('PosToNegChunk', '1--20x5', list(range(1,-21,-5))),
    ('PosToPosChunkInv', '20-1x5', list(range(20,0,-5))),
    ('NegToPosChunkInv', '-20-1x5', list(range(-20,2,5))),
    ('NegToNegChunkInv', '-20--1x5', list(range(-20,0,5))),
    ('PosToNegChunkInv', '20--1x5', list(range(20,-2,-5))),
    ('PosToPosNegChunkInv', '20-1x-1', list(range(20,0,-1))),
    ('PosToPosFill', '1-20y5', list(_yrange(1,21,5))),
    ('NegToPosFill', '-1-20y5', list(_yrange(-1,21,5))),
    ('NegToNegFill', '-1--20y5', list(_yrange(-1,-21,-5))),
    ('PosToNegFill', '1--20y5', list(_yrange(1,-21,-5))),
    ('PosToPosFillInv', '20-1y5', list(_yrange(20,0,-5))),
    ('NegToPosFillInv', '-20-1y5', list(_yrange(-20,2,5))),
    ('NegToNegFillInv', '-20--1y5', list(_yrange(-20,0,5))),
    ('PosToNegFillInv', '20--1y5', list(_yrange(20,-2,-5))),
    ('PosToPosStagger', '1-20:5', list(_srange(1,21,5))),
    ('NegToPosStagger', '-1-20:5', list(_srange(-1,21,5))),
    ('NegToNegStagger', '-1--20:5', list(_srange(-1,-21,-5))),
    ('PosToNegStagger', '1--20:5', list(_srange(1,-21,-5))),
    ('PosToPosStaggerInv', '20-1:5', list(_srange(20,0,-5))),
    ('NegToPosStaggerInv', '-20-1:5', list(_srange(-20,2,5))),
    ('NegToNegStaggerInv', '-20--1:5', list(_srange(-20,0,5))),
    ('PosToNegStaggerInv', '20--1:5', list(_srange(20,-2,-5)))]

HI_RANGES = [
    # high value permutations of signed integer ranges, these will be permuted with the LO_RANGES for testing
    ('PosToPos', '21-30', list(range(21,31,1))),
    ('NegToPos', '-21-30', list(range(-21,31,1))),
    ('NegToNeg', '-21--30', list(range(-21,-31,-1))),
    ('PosToNeg', '21--30', list(range(21,-31,-1))),
    ('PosToPosInv', '30-21', list(range(30,20,-1))),
    ('NegToPosInv', '-30-21', list(range(-30,22,1))),
    ('NegToNegInv', '-30--21', list(range(-30,-20,1))),
    ('PosToNegInv', '30--21', list(range(30,-22,-1))),
    ('PosToPosChunk', '21-30x5', list(range(21,31,5))),
    ('NegToPosChunk', '-21-30x5', list(range(-21,31,5))),
    ('NegToNegChunk', '-21--30x5', list(range(-21,-31,-5))),
    ('PosToNegChunk', '21--30x5', list(range(21,-31,-5))),
    ('PosToPosChunkInv', '30-21x5', list(range(30,20,-5))),
    ('NegToPosChunkInv', '-30-21x5', list(range(-30,22,5))),
    ('NegToNegChunkInv', '-30--21x5', list(range(-30,-20,5))),
    ('PosToNegChunkInv', '30--21x5', list(range(30,-22,-5))),
    ('PosToPosFill', '21-30y5', list(_yrange(21,31,5))),
    ('NegToPosFill', '-21-30y5', list(_yrange(-21,31,5))),
    ('NegToNegFill', '-21--30y5', list(_yrange(-21,-31,-5))),
    ('PosToNegFill', '21--30y5', list(_yrange(21,-31,-5))),
    ('PosToPosFillInv', '30-21y5', list(_yrange(30,20,-5))),
    ('NegToPosFillInv', '-30-21y5', list(_yrange(-30,22,5))),
    ('NegToNegFillInv', '-30--21y5', list(_yrange(-30,-20,5))),
    ('PosToNegFillInv', '30--21y5', list(_yrange(30,-22,-5))),
    ('PosToPosStagger', '21-30:5', list(_srange(21,31,5))),
    ('NegToPosStagger', '-21-30:5', list(_srange(-21,31,5))),
    ('NegToNegStagger', '-21--30:5', list(_srange(-21,-31,-5))),
    ('PosToNegStagger', '21--30:5', list(_srange(21,-31,-5))),
    ('PosToPosStaggerInv', '30-21:5', list(_srange(30,20,-5))),
    ('NegToPosStaggerInv', '-30-21:5', list(_srange(-30,22,5))),
    ('NegToNegStaggerInv', '-30--21:5', list(_srange(-30,-20,5))),
    ('PosToNegStaggerInv', '30--21:5', list(_srange(30,-22,-5)))]

for lo in LO_RANGES:
    FRAME_SET_SHOULD_SUCCEED.append(lo)
    for hi in HI_RANGES:
        name = 'CommaSep{0}To{1}'.format(lo[0], hi[0])
        test = ','.join([lo[1], hi[1]])
        expect = list(_uchain(lo[2], hi[2]))
        FRAME_SET_SHOULD_SUCCEED.append((name, test, expect))

FRAME_SET_SHOULD_FAIL = [
    ("PosWChunkChar", "1x5"),
    ("NegWChunkChar", "-1x5"),
    ("PosWFillChar", "1y5"),
    ("NegWFillChar", "-1y5"),
    ("PosWStaggerChar", "1:5"),
    ("NegWStaggerChar", "-1:5"),
    ("PosWSepChar", "1-"),
    ("NegWSepChar", "-1-"),
    ("BadAlphaChars", "bilbo"),
    ("RangeWDupeSpecialChar", "1-20x:y5"),
    ("RangeWBadCaseChunkChar", "1-20X5"),
    ("RangeWBadCaseFillChar", "1-20Y5"),
    ("RangeWChunkZero", "1-20x0"),
    ("RangeWFillZero", "1-20y0"),
    ("RangeWStaggerZero", "1-20:0"),
    ("RangeWNegChunk", "1-20x-5"),
    ("RangeWNegFill", "1-20y-5"),
    ("RangeWNegStagger", "1-20:-5"),
    ("NonNumericChar", "a"),
    ("NonNumericRange", "a-z"),
    ("NonNumericSeq", ["a", "z"]),
    ("ActualNone", None),
]


FRAME_SET_FROM_RANGE_SHOULD_SUCCEED = [
    # individual frames
    ('Zero', 0, 0, 1, '0'),
    ('Pos', 1, 1, 1, '1'),
    # ranges
    ('PosToPos', 1, 20, 1, '1-20'),
    ('NegToPos', -1, 1, 1, '-1-1'),
    ('PosToNeg', 1, -1, 1, '1--1'),
    ('PosToPosInv', 20, 1, 1, '20-1'),
    ('NegToPosInv', -20, 1, 1, '-20-1'),
    ('NegToNegInv', -20, -1, 1, '-20--1'),
    ('PosToNegInv', 20, -1, 1, '20--1'),
    ('PosToPosChunk', 1, 20, 5, '1-20x5'),
    ('NegToPosChunk', -1, 20, 5, '-1-20x5'),
    ('NegToNegChunk', -1, -20, 5, '-1--20x5'),
    ('PosToNegChunk', 1, -20, 5, '1--20x5'),
    ('PosToPosChunkInv', 20, 1, 5, '20-1x5'),
    ('NegToPosChunkInv', -20, 1, 5, '-20-1x5'),
    ('NegToNegChunkInv', -20, -1, 5, '-20--1x5'),
    ('PosToNegChunkInv', 20, -1, 5, '20--1x5'),
    ('PosToPosNegChunkInv', 20, 1, -1, '20-1x-1'),
]


class TestFrameSet(unittest.TestCase):
    """
    Exercise the TestFrame object.  Due to the sheer number of permutations, we'll add most tests dynamically.
    """

    def _check___init___range(self, test, expect):
        """
        Harness to test if the FrameSet.__init__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'FrameSet("{0}")._frange != {0}: got {1}'
        r = f._frange
        self.assertEqual(r, native_str(test), m.format(test, r))
        m = u'FrameSet("{0}")._frange returns {1}: got {2}'
        self.assertIsInstance(r, native_str, m.format(test, native_str, type(r)))

    def _check___init___items(self, test, expect):
        """
        Harness to test if the FrameSet.__init__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'FrameSet("{0}")._items != {1}: got {2}'
        r = f._items
        self.assertEqual(r, set(expect), m.format(test, set(expect), r))
        m = u'FrameSet("{0}")._FrameSet__items returns {1}: got {2}'
        self.assertIsInstance(r, frozenset, m.format(test, frozenset, type(r)))

    def _check___init___order(self, test, expect):
        """
        Harness to test if the FrameSet.__init__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'FrameSet("{0}")._order != {1}: got {2}'
        r = f._order
        self.assertEqual(r, tuple(expect), m.format(test, tuple(expect), r))
        m = u'FrameSet("{0}")._order returns {1}: got {2}'
        self.assertIsInstance(r, tuple, m.format(test, tuple, type(r)))

    def _check___init____malformed(self, test):
        """
        Harness to test if the FrameSet.__init__ call properly handles malformed strings.
        :param test: the string to pass to FrameSet
        :return: None
        """
        try:
            r = FrameSet(test)
        except ParseException as err:
            r = err
        except Exception as err:
            r = err
        m = u'FrameSet("{0}") should fail: got {1}'
        self.assertIsInstance(r, ParseException, m.format(test, r))

    def _check___str__(self, test, expect):
        """
        Harness to test if the FrameSet.__str__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'str(FrameSet("{0}")) != {0}: got {1}'
        r = str(f)
        self.assertEqual(r, native_str(test), m.format(test, r))
        m = u'str(FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(r, native_str, m.format(test, native_str, type(r)))

    def _check___len__(self, test, expect):
        """
        Harness to test if the FrameSet.__len__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'len(FrameSet("{0}")) != {1}: got {2}'
        r = len(f)
        self.assertEqual(r, len(expect), m.format(test, len(expect), r))
        m = u'len(FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check___getitem__(self, test, expect):
        """
        Harness to test if the FrameSet.__getitem__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        i = len(expect) // 2
        m = u'FrameSet("{0}")[{1}] != {2}: got {3}'
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertRaises(IndexError, f.__getitem__, i)
            return
        try:
            r = f[i]
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[i], m.format(test, i, expect[i], r))
        m = u'FrameSet("{0}")[{1}] returns {2}: got {3}'
        self.assertIsInstance(r, int, m.format(test, i, int, type(r)))
        try:
            r = f[:-1:2]
        except Exception as err:
            r = repr(err)
        e = tuple(expect[:-1:2])
        m = u'FrameSet("{0}")[:1:2] != {1}: got {2}'
        self.assertEqual(r, e, m.format(test, e, r))

    def _check_start(self, test, expect):
        """
        Harness to test if the FrameSet.start call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'FrameSet("{0}").start() != {1}: got {2}'
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertRaises(IndexError, f.start)
            return
        try:
            r = f.start()
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[0], m.format(test, expect[0], r))
        m = u'FrameSet("{0}").start() returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check_end(self, test, expect):
        """
        Harness to test if the FrameSet.end call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'FrameSet("{0}").end() != {1}: got {2}'
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertRaises(IndexError, f.end)
            return
        try:
            r = f.end()
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[-1], m.format(test, expect[-1], r))
        m = u'FrameSet("{0}").end() returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check_index(self, test, expect):
        """
        Harness to test if the FrameSet.index call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertRaises(IndexError, f.frame, 0)
            return
        i = expect[len(expect) // 2]
        m = u'FrameSet("{0}").index({1}) != {2}: got {3}'
        try:
            r = f.index(i)
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect.index(i), m.format(test, i, expect.index(i), r))
        m = u'FrameSet("{0}").index({1}) returns {2}: got {3}'
        self.assertIsInstance(r, int, m.format(test, i, int, type(r)))

    def _check_frame(self, test, expect):
        """
        Harness to test if the FrameSet.frame call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertRaises(IndexError, f.frame, 0)
            return
        i = len(expect) // 2
        m = u'FrameSet("{0}").frame({1}) != {2}: got {3}'
        try:
            r = f.frame(i)
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[i], m.format(test, i, expect[i], r))
        m = u'FrameSet("{0}").frame({1}) returns {2}: got {3}'
        self.assertIsInstance(r, int, m.format(test, i, int, type(r)))

    def _check_hasFrameTrue(self, test, expect):
        """
        Harness to test if the FrameSet.hasFrame call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertFalse(f.hasFrame(1))
            return
        i = max(expect)
        m = u'FrameSet("{0}").hasFrame({1}) != {2}: got {3}'
        r = f.hasFrame(i)
        self.assertTrue(r, m.format(test, i, i in expect, r))
        m = u'FrameSet("{0}").frame({1}) returns {2}: got {3}'
        self.assertIsInstance(r, bool, m.format(test, i, bool, type(r)))

    def _check_hasFrameFalse(self, test, expect):
        """
        Harness to test if the FrameSet.hasFrame call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is expected to always fail
        if not test and not expect:
            self.assertFalse(f.hasFrame(1))
            return
        i = max(expect) + 1
        m = u'FrameSet("{0}").hasFrame({1}) != {2}: got {3}'
        r = f.hasFrame(i)
        self.assertFalse(r, m.format(test, i, i in expect, r))
        m = u'FrameSet("{0}").frame({1}) returns {2}: got {3}'
        self.assertIsInstance(r, bool, m.format(test, i, bool, type(r)))

    def _check___iter__(self, test, expect):
        """
        Harness to test if the FrameSet.__iter__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'list(FrameSet("{0}")) != {1}: got {2}'
        r = f.__iter__()
        self.assertEqual(list(r), expect, m.format(test, expect, list(r)))
        m = u'FrameSet("{0}").__iter__ returns {1}: got {2}'
        self.assertIsInstance(r, types.GeneratorType, m.format(test, types.GeneratorType, type(r)))

    def _check_canSerialize(self, test, expect):
        """
        Harness to test if the FrameSet.__getstate__ and FrameSet.__setstate__ calls allowing pickling.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        f2 = pickle.loads(pickle.dumps(f))
        m = u'FrameSet("{0}") does not pickle correctly'
        self.assertIsInstance(f2, FrameSet, m.format(test))
        self.assertTrue(str(f) == str(f2) and list(f) == list(f2), m.format(test))
        # test old objects being unpickled through new lib
        state = {'__frange': f._frange, '__set': set(f._items), '__list': list(f._order)}
        f2 = FrameSet.__new__(FrameSet)
        f2.__setstate__(state)
        self.assertTrue(str(f) == str(f2) and list(f) == list(f2), m.format(test))

    def _check_frameRange(self, test, expect):
        """
        Harness to test if the FrameSet.frameRange call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet always has a frameRange of ''
        if not test and not expect:
            self.assertEqual(f.frameRange(), '')
            return

        p1 = r'((?<![xy:-])-?\d+)'
        l = max([max([len(i) for i in re.findall(p1, str(f))]) + 1, 4])

        p2 = r'(-?\d+)(?:(-)(-?\d+)([xy:]\d+)?)?'
        def replace(match):
            start, sep, end, step = match.groups()
            if start:
                start = start.zfill(l)
            if end:
                end = end.zfill(l)
            return ''.join(o for o in [start, sep, end, step] if o)
        expect = re.sub(p2, replace, str(f))
        try:
            r = f.frameRange(l)
        except Exception as err:
            r = repr(err)
        m = u'FrameSet("{0}").frameRange({1}) != "{2}": got "{3}"'
        self.assertEqual(r, expect, m.format(test, l, expect, r))

        m = u'FrameSet("{0}").frameRange({1}) returns {2}: got {3}'
        self.assertIsInstance(r, native_str, m.format(test, l, native_str, type(r)))

    def _check_invertedFrameRange(self, test, expect):
        """
        Harness to test if the FrameSet.invertedFrameRange call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'FrameSet("{0}").invertedFrameRange() != "{1}": got "{2}"'
        r = f.invertedFrameRange()
        t = sorted(f)
        c = sorted(FrameSet(r) if r else [])
        # the empty FrameSet will always return '' for inverted and normal
        # FrameRange
        if not test and not expect:
            self.assertEqual(r, '')
        else:
            e = [i for i in range(t[0], t[-1]) if i not in t]
            self.assertEqual(c, e, m.format(test, e, c))
        m = u'FrameSet("{0}").invertedFrameRange() returns {1}: got {2}'
        self.assertIsInstance(r, native_str, m.format(test, native_str, type(r)))

    def _check_normalize(self, test, expect):
        """
        Harness to test if the FrameSet.normalize call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        m = u'set(FrameSet("{0}").normalize()) != {1}: got {2}'
        r = f.normalize()
        self.assertEqual(set(f), set(r), m.format(test, set(expect), set(r)))
        m = u'FrameSet("{0}").normalize() returns {1}: got {2}'
        self.assertIsInstance(r, FrameSet, m.format(test, FrameSet, type(r)))

    def _check_isFrameRange(self, test, expect):
        """
        Harness to test if the FrameSet.isFrameRange call works properly.
        :param test: the string to pass to FrameSet.isFrameRange
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        r = FrameSet.isFrameRange(test)
        m = u'FrameSet.isFrameRange("{0}") != {1}: got {2}'
        self.assertEqual(r, expect, m.format(test, expect, r))
        m = u'FrameSet.isFrameRange("{0}") returns {1}: got {2}'
        self.assertIsInstance(r, bool, m.format(test, bool, type(r)))

    def _check_fromIterable(self, expect, iterable):
        """
        Harness to test if the FrameSet.fromIterable call works properly.
        :param expect: the string to use to build the expected FrameRange, which will be normalized for comparison
        :param iterable: the iterable to test
        :return: None
        """
        e = FrameSet(expect)
        r = FrameSet.from_iterable(iterable)
        m = u'FrameSet.fromIterable({0}) != {1!r}: got {2!r}'
        self.assertEqual(r, e, m.format(iterable, e, r))
        m = u'FrameSet.fromIterable({0}) returns {1}: got {2}'
        self.assertIsInstance(r, FrameSet, m.format(expect, FrameSet, type(r)))

    def _check___repr__(self, test, expect):
        """
        Harness to test if the FrameSet.__repr__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        e = 'FrameSet("{0}")'.format(test)
        m = u'repr(FrameSet("{0}")) != {1}: got {2}'
        self.assertEqual(repr(f), e, m.format(test, e, repr(f)))
        m = u'repr(FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(repr(f), native_str, m.format(test, native_str, type(repr(f))))

    def _check___reversed__(self, test, expect):
        """
        Harness to test if the FrameSet.__reversed__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        e = list(reversed(expect))
        r = reversed(f)
        m = u'reversed(FrameSet("{0}")) != {1}: got {2}'
        self.assertEqual(list(r), e, m.format(test, e, r))
        m = u'reversed(FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(r, types.GeneratorType, m.format(test, types.GeneratorType, type(r)))

    def _check___contains__(self, test, expect):
        """
        Harness to test if the FrameSet.__contains__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        e = expect[-1] if len(expect) else None
        should_succeed = e in f
        e = (max(expect) + 1) if len(expect) else None
        should_fail = e in f
        m = u'{0} in FrameSet("{1}"))'
        # the empty FrameSet contains nothing
        if not test and not expect:
            self.assertFalse(should_succeed, m.format(e, test))
            self.assertFalse(should_fail, m.format(e, test))
        else:
            self.assertTrue(should_succeed, m.format(e, test))
            self.assertFalse(should_fail, m.format(e, test))
        m = u'FrameSet("{0}").__contains__ returns {1}: got {2}'
        self.assertIsInstance(should_succeed, bool, m.format(test, bool, type(should_succeed)))
        self.assertIsInstance(should_fail, bool, m.format(test, bool, type(should_fail)))

    def _check___hash__(self, test, expect):
        """
        Harness to test if the FrameSet.__hash__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        try:
            r = hash(f)
        except Exception as err:
            r = err
        m = u'hash(FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check___lt__(self, test, expect):
        """
        Harness to test if the FrameSet.__lt__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is less than everything, except for itself
        if not test and not expect:
            self.assertTrue(f < FrameSet('1'))
            self.assertTrue(f < FrameSet('-1'))
            self.assertFalse(f < expect)
            return
        r = FrameSet.from_iterable(expect + [max(expect) + 1])
        should_succeed = f < r
        should_fail = r < f
        m = u'FrameSet("{0}") < FrameSet("{1}")'
        self.assertTrue(should_succeed, m.format(test, r))
        self.assertFalse(should_fail, m.format(r, test))
        m = u'FrameSet("{0}") < FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(should_succeed, bool, m.format(test, r, bool, type(should_succeed)))
        self.assertIsInstance(should_fail, bool, m.format(r, test, bool, type(should_fail)))

    def _check___le__(self, test, expect):
        """
        Harness to test if the FrameSet.__le__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is less than everything, equal only to itself
        if not test and not expect:
            self.assertTrue(f <= FrameSet('1'))
            self.assertTrue(f <= FrameSet('-1'))
            self.assertTrue(f <= expect)
            return
        for i in [expect, expect + [max(expect) + 1]]:
            r = FrameSet.from_iterable(i)
            should_succeed = f <= r
            m = u'FrameSet("{0}") <= FrameSet("{1}")'
            self.assertTrue(should_succeed, m.format(test, r))
            m = u'FrameSet("{0}") <= FrameSet("{1}") returns {2}: got {3}'
            self.assertIsInstance(should_succeed, bool, m.format(test, r, bool, type(should_succeed)))

    def _check___eq__(self, test, expect):
        """
        Harness to test if the FrameSet.__eq__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        r = FrameSet(','.join((str(i) for i in expect)))
        should_succeed = f == r
        m = u'FrameSet("{0}") == FrameSet("{1}")'
        self.assertTrue(should_succeed, m.format(test, r))
        m = u'FrameSet("{0}") == FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(should_succeed, bool, m.format(test, r, bool, type(should_succeed)))

    def _check___ne__(self, test, expect):
        """
        Harness to test if the FrameSet.__ne__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is not equal to anything, except for itself
        if not test and not expect:
            self.assertTrue(f != FrameSet('1'))
            self.assertTrue(f != FrameSet('-1'))
            self.assertFalse(f != expect)
            return
        r = FrameSet(','.join((str(i) for i in (expect + [max(expect) + 1]))))
        should_succeed = f != r
        m = u'FrameSet("{0}") != FrameSet("{1}")'
        self.assertTrue(should_succeed, m.format(test, r))
        m = u'FrameSet("{0}") != FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(should_succeed, bool, m.format(test, r, bool, type(should_succeed)))

    def _check___ge__(self, test, expect):
        """
        Harness to test if the FrameSet.__ge__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is greater than nothing, except for itself
        if not test and not expect:
            self.assertFalse(f >= FrameSet('1'))
            self.assertFalse(f >= FrameSet('-1'))
            self.assertTrue(f >= expect)
            return
        for i in [expect, expect[:-1]]:
            try:
                r = FrameSet.from_iterable(i)
            except ParseException:
                # this will happen if len(expect) == 1
                continue
            should_succeed = f >= r
            m = u'FrameSet("{0}") >= FrameSet("{1}"'
            self.assertTrue(should_succeed, m.format(test, r))
            m = u'FrameSet("{0}") >= FrameSet("{1}") returns {2}: got {3}'
            self.assertIsInstance(should_succeed, bool, m.format(test, r, bool, type(should_succeed)))

    def _check___gt__(self, test, expect):
        """
        Harness to test if the FrameSet.__gt__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is greater than nothing, except for itself
        if not test and not expect:
            self.assertFalse(f > FrameSet('1'))
            self.assertFalse(f > FrameSet('-1'))
            self.assertFalse(f > expect)
            return
        try:
            r = FrameSet.from_iterable(expect[:-1])
        except ParseException:
            # this will happen if len(expect) == 1
            return
        should_succeed = f > r
        should_fail = r > f
        m = u'FrameSet("{0}") > FrameSet("{1}")'
        self.assertTrue(should_succeed, m.format(test, r))
        self.assertFalse(should_fail, m.format(r, test))
        m = u'FrameSet("{0}") > FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(should_succeed, bool, m.format(test, r, bool, type(should_succeed)))
        self.assertIsInstance(should_fail, bool, m.format(r, test, bool, type(should_fail)))

    def _check___and__(self, test, expect):
        """
        Harness to test if the FrameSet.__and__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = f & t
        e = FrameSet.from_iterable(set(expect) & set(v), sort=True)
        m = u'FrameSet("{0}") & FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(f, t, e))
        m = u'FrameSet("{0}") & FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check___rand__(self, test, expect):
        """
        Harness to test if the FrameSet.__rand__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = t & f
        e = FrameSet.from_iterable(set(v) & set(expect), sort=True)
        m = u'FrameSet("{0}") & FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(t, f, e))
        m = u'FrameSet("{0}") & FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(t, test, FrameSet, type(r)))

    def _check___sub__(self, test, expect):
        """
        Harness to test if the FrameSet.__sub__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = f - t
        e = FrameSet.from_iterable(set(expect) - set(v), sort=True)
        m = u'FrameSet("{0}") - FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(f, t, e))
        m = u'FrameSet("{0}") - FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check___rsub__(self, test, expect):
        """
        Harness to test if the FrameSet.__rsub__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = t - f
        e = FrameSet.from_iterable(set(v) - set(expect), sort=True)
        m = u'FrameSet("{0}") - FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(t, f, e))
        m = u'FrameSet("{0}") - FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(t, test, FrameSet, type(r)))

    def _check___or__(self, test, expect):
        """
        Harness to test if the FrameSet.__or__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = f | t
        e = FrameSet.from_iterable(set(expect) | set(v), sort=True)
        m = u'FrameSet("{0}") | FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(f, t, e))
        m = u'FrameSet("{0}") | FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check___ror__(self, test, expect):
        """
        Harness to test if the FrameSet.__ror__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = t | f
        e = FrameSet.from_iterable(set(v) | set(expect), sort=True)
        m = u'FrameSet("{0}") | FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(t, f, e))
        m = u'FrameSet("{0}") | FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(t, test, FrameSet, type(r)))

    def _check___xor__(self, test, expect):
        """
        Harness to test if the FrameSet.__xor__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = f ^ t
        e = FrameSet.from_iterable(set(expect) ^ set(v), sort=True)
        m = u'FrameSet("{0}") ^ FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(f, t, e))
        m = u'FrameSet("{0}") ^ FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check___rxor__(self, test, expect):
        """
        Harness to test if the FrameSet.__rxor__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        v = [i + max(expect) + 1 for i in expect] or list(range(999, 1999))
        t = FrameSet.from_iterable(v)
        r = t ^ f
        e = FrameSet.from_iterable(set(v) ^ set(expect), sort=True)
        m = u'FrameSet("{0}") ^ FrameSet("{1}") != FrameSet("{2}")'
        self.assertEqual(r, e, m.format(t, f, e))
        m = u'FrameSet("{0}") ^ FrameSet("{1}") returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(t, test, FrameSet, type(r)))

    def _check_isdisjoint(self, test, expect):
        """
        Harness to test if the FrameSet.isdisjoint call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is the disjoint of everything, including itself
        if not test and not expect:
            self.assertTrue(f.isdisjoint(FrameSet('1')))
            self.assertTrue(f.isdisjoint(FrameSet('-1')))
            self.assertTrue(f.isdisjoint(expect))
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.isdisjoint(t)
            e = set(expect).isdisjoint(v)
            m = u'FrameSet("{0}").isdisjoint(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").isdisjoint(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, bool, m.format(test, t, bool, type(r)))

    def _check_issubset(self, test, expect):
        """
        Harness to test if the FrameSet.issubset call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is the subset of everything, including itself
        if not test and not expect:
            self.assertTrue(f.issubset(FrameSet('1')))
            self.assertTrue(f.issubset(FrameSet('-1')))
            self.assertTrue(f.issubset(expect))
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.issubset(t)
            e = set(expect).issubset(v)
            m = u'FrameSet("{0}").issubset(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").issubset(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, bool, m.format(test, t, bool, type(r)))

    def _check_issuperset(self, test, expect):
        """
        Harness to test if the FrameSet.issuperset call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the empty FrameSet is the superset of everything, except itself
        if not test and not expect:
            self.assertFalse(f.issuperset(FrameSet('1')))
            self.assertFalse(f.issuperset(FrameSet('-1')))
            self.assertTrue(f.issuperset(expect))
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.issuperset(t)
            e = set(expect).issuperset(v)
            m = u'FrameSet("{0}").issuperset(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").issuperset(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, bool, m.format(test, t, bool, type(r)))

    def _check_union(self, test, expect):
        """
        Harness to test if the FrameSet.union call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the union of the empty FrameSet with any other is always the other
        if not test and not expect:
            self.assertEqual(f.union(FrameSet('1')), FrameSet('1'))
            self.assertEqual(f.union(FrameSet('-1')), FrameSet('-1'))
            self.assertEqual(f.union(expect), FrameSet.from_iterable(expect, sort=True))
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.union(t)
            e = FrameSet.from_iterable(set(expect).union(v), sort=True)
            m = u'FrameSet("{0}").union(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").union(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check_intersection(self, test, expect):
        """
        Harness to test if the FrameSet.intersection call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the intersection of the empty FrameSet with any other is always the empty FrameSet
        if not test and not expect:
            self.assertEqual(f.intersection(FrameSet('1')), f)
            self.assertEqual(f.intersection(FrameSet('-1')), f)
            self.assertEqual(f.intersection(expect), f)
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.intersection(t)
            e = FrameSet.from_iterable(set(expect).intersection(v), sort=True)
            m = u'FrameSet("{0}").intersection(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").intersection(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check_difference(self, test, expect):
        """
        Harness to test if the FrameSet.difference call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the difference of the empty FrameSet with any other is always the empty FrameSet
        if not test and not expect:
            self.assertEqual(f.intersection(FrameSet('1')), f)
            self.assertEqual(f.intersection(FrameSet('-1')), f)
            self.assertEqual(f.intersection(expect), f)
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.difference(t)
            e = FrameSet.from_iterable(set(expect).difference(v), sort=True)
            m = u'FrameSet("{0}").difference(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").difference(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, FrameSet, m.format(test, t, FrameSet, type(r)))

    def _check_symmetric_difference(self, test, expect):
        """
        Harness to test if the FrameSet.symmetric_difference call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        # the symmetric_difference of the empty FrameSet with any other is always the empty FrameSet
        if not test and not expect:
            self.assertEqual(f.intersection(FrameSet('1')), f)
            self.assertEqual(f.intersection(FrameSet('-1')), f)
            self.assertEqual(f.intersection(expect), f)
            return
        for v in [[expect[0]], expect, expect + [max(expect)+1], [i + max(expect) + 1 for i in expect]]:
            t = FrameSet.from_iterable(v)
            r = f.symmetric_difference(t)
            e = FrameSet.from_iterable(set(expect).symmetric_difference(v), sort=True)
            m = u'FrameSet("{0}").symmetric_difference(FrameSet("{1}")) != {2}'
            self.assertEqual(r, e, m.format(t, f, e))
            m = u'FrameSet("{0}").symmetric_difference(FrameSet("{1}")) returns {2}: got {3}'
            self.assertIsInstance(r, FrameSet, m.format(test, t,
                                                                FrameSet, type(r)))

    def _check_copy(self, test, expect):
        """
        Harness to test if the FrameSet.copy call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = FrameSet(test)
        r = f.copy()
        self.assertIsNot(f, r)
        self.assertEqual(f, r)


# due to the sheer number of combinations, we build the bulk of our tests on to TestFrameSet dynamically
for name, tst, exp in FRAME_SET_SHOULD_SUCCEED:
    setattr(
        TestFrameSet, 'testFrameSet%sInitSetsRange' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___init___range(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sInitSetsItems' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___init___items(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sInitSetsOrder' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___init___order(self, t, e))
    setattr(
        TestFrameSet, 'testFromIterable%s' % name,
        lambda self, e=tst, i=exp: TestFrameSet._check_fromIterable(self, e, i))
    setattr(
        TestFrameSet, 'testFrameSet%sIndex' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_index(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sFrame' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_frame(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sHasFrameTrue' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_hasFrameTrue(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sHasFrameFalse' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_hasFrameTrue(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sStart' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_start(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sEnd' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_end(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sFrameRange' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_frameRange(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sInvertedFrameRange' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_invertedFrameRange(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sNormalize' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_normalize(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sSerialize' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_canSerialize(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sGetItem' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___getitem__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sLen' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___len__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sStr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___str__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sRepr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___repr__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sIter' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___iter__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sReversed' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___reversed__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sContains' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___contains__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sHash' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___hash__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sLessThan' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___lt__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sLessEqual' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___le__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sEqual' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___eq__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sNotEqual' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___ne__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sGreaterEqual' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___ge__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sGreaterThan' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___gt__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sAnd' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___and__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sRightAnd' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___rand__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sSub' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___sub__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sRightSub' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___rsub__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sOr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___or__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sRightOr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___ror__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sExclusiveOr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___xor__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sRightExclusiveOr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___rxor__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sIsDisjoint' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_isdisjoint(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sIsSubset' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_issubset(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sIsSubset' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_issuperset(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sUnion' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_union(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sIntersection' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_intersection(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sDifference' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_difference(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sSymmetricDifference' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_symmetric_difference(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sCopy' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_copy(self, t, e))
    setattr(
        TestFrameSet, 'testIsFrameRange%sShouldSucceed' % name,
        lambda self, t=tst: TestFrameSet._check_isFrameRange(self, t, True))

for name, tst in FRAME_SET_SHOULD_FAIL:
    setattr(
        TestFrameSet, 'testFrameSet%sInitHandlesMalformed' % name,
        lambda self, t=tst: TestFrameSet._check___init____malformed(self, t))
    setattr(
        TestFrameSet, 'testIsFrameRange%sShouldFail' % name,
        lambda self, t=tst: TestFrameSet._check_isFrameRange(self, t, False))


class TestFramesToFrameRange(unittest.TestCase):
    """
    Exercise the frameToRange func.  Due to the sheer number of permutations, we'll add most tests dynamically.
    """

    def _check_frameToRangeEquivalence(self, test, expect):
        f = FrameSet(test)
        frange = framesToFrameRange(expect, sort=False)
        r = FrameSet(frange)
        m = '{0!r} != {1!r}'
        self.assertEqual(f, r, m.format(f, r))
        m = '{0!r} != {1!r} ; got type {2!r}'
        self.assertIsInstance(frange, native_str, m.format(frange, native_str, type(frange)))

# due to the sheer number of combinations, we build the bulk of our tests on to TestFramesToFrameRange dynamically
for name, tst, exp in FRAME_SET_SHOULD_SUCCEED:
    setattr(
        TestFramesToFrameRange, 'testFramesToRangeEquivalence%s' % name,
        lambda self, t=tst, e=exp: TestFramesToFrameRange._check_frameToRangeEquivalence(self, t, e))


class TestFrameSetFromRangeConstructor(unittest.TestCase):
    """
    Exercise the TestFrame.from_range() constructor. Due to the sheer number of permutations, we'll add most tests dynamically.
    """

    def _check_fromRange(self, start, end, step, expect):
        """
        Harness to test if the FrameSet.fromRange call works properly.
        :param expect: the string to use to build the expected FrameSet, which will be normalized for comparison
        :param start: the start frame
        :param end: the end frame
        :return: None
        """
        e = FrameSet(expect)
        r = FrameSet.from_range(start, end, step)
        m = u'FrameSet.fromRange({0}, {1}) != {2!r}: got {3!r}'
        self.assertEqual(r, e, m.format(start, end, e, r))
        m = u'FrameSet.fromRange({0}, {1}) returns {2}: got {3}'
        self.assertIsInstance(r, FrameSet, m.format(start, end, FrameSet, type(r)))


# add tests dynamically
for name, start, end, step_, exp in FRAME_SET_FROM_RANGE_SHOULD_SUCCEED:
    setattr(
        TestFrameSetFromRangeConstructor, 'testFromRange%s' % name,
        lambda self, s=start, e=end, step=step_, exp=exp: TestFrameSetFromRangeConstructor._check_fromRange(self, s, e, step, exp))


if __name__ == '__main__':
    unittest.main(verbosity=1)


