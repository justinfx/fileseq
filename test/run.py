#!/usr/bin/python

import unittest
import cPickle
import sys
import os
import re
import types
from itertools import chain

TEST_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(TEST_DIR, "../src")
sys.path.insert(0, SRC_DIR)
os.chdir(TEST_DIR)

import fileseq

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
    whole = range(first, last, 1 if incr >= 0 else -1)
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
    whole = range(first, last, 1 if incr >= 0 else -1)
    sent = set()
    for stagger in xrange(abs(incr), 0, -1):
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
    # individual frames
    ('Zero', '0', [0]),
    ('NegZero', '-0', [0]),
    ('Pos', '1', [1]),
    ('Neg', '-1', [-1]),
    # permutations on comma separated individual frames
    ('CommaSepPos', '1,3,17', [1,3,17]),
    ('CommaSepNeg', '-1,-3,-17', [-1,-3,-17]),
    ('CommaSepMix', '1,-3,17', [1,-3,17]),
    ('CommaSepPosInv', '17,3,1', [17,3,1]),
    ('CommaSepNegInv', '-17,-3,-1', [-17,-3,-1]),
    ('CommaSepMixInv', '17,-3,1', [17,-3,1]),
    # args that str(arg) cast to a valid FrameSet
    ('PosInt', 1, [1]),
    ('NegInt', -1, [-1]),
    ('FrameSet', fileseq.FrameSet("1-20"), list(xrange(1,21))),
    # unicode args that are the equivalent of a valid FrameSet
    ('UnicodeEquivalentRange', u'-1--20', list(xrange(-1,-21,-1))),
    ('UnicodeEquivalentRangeBatch', u'-1--20x5', list(xrange(-1,-21,-5))),
    ('UnicodeEquivalentRangeFill', u'-1--20y5', list(_yrange(-1,-21,-5))),
    ('UnicodeEquivalentRangeStagger', u'-1--20:5', list(_srange(-1,-21,-5))),
]

LO_RANGES = [
    # low value permutations of signed integer ranges, these will all be individually tested
    ('PosToPos', '1-20', list(xrange(1,21,1))),
    ('NegToPos', '-1-20', list(xrange(-1,21,1))),
    ('NegToNeg', '-1--20', list(xrange(-1,-21,-1))),
    ('PosToNeg', '1--20', list(xrange(1,-21,-1))),
    ('PosToPosInv', '20-1', list(xrange(20,0,-1))),
    ('NegToPosInv', '-20-1', list(xrange(-20,2,1))),
    ('NegToNegInv', '-20--1', list(xrange(-20,0,1))),
    ('PosToNegInv', '20--1', list(xrange(20,-2,-1))),
    ('PosToPosChunk', '1-20x5', list(xrange(1,21,5))),
    ('NegToPosChunk', '-1-20x5', list(xrange(-1,21,5))),
    ('NegToNegChunk', '-1--20x5', list(xrange(-1,-21,-5))),
    ('PosToNegChunk', '1--20x5', list(xrange(1,-21,-5))),
    ('PosToPosChunkInv', '20-1x5', list(xrange(20,0,-5))),
    ('NegToPosChunkInv', '-20-1x5', list(xrange(-20,2,5))),
    ('NegToNegChunkInv', '-20--1x5', list(xrange(-20,0,5))),
    ('PosToNegChunkInv', '20--1x5', list(xrange(20,-2,-5))),
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
    ('PosToPos', '21-30', list(xrange(21,31,1))),
    ('NegToPos', '-21-30', list(xrange(-21,31,1))),
    ('NegToNeg', '-21--30', list(xrange(-21,-31,-1))),
    ('PosToNeg', '21--30', list(xrange(21,-31,-1))),
    ('PosToPosInv', '30-21', list(xrange(30,20,-1))),
    ('NegToPosInv', '-30-21', list(xrange(-30,22,1))),
    ('NegToNegInv', '-30--21', list(xrange(-30,-20,1))),
    ('PosToNegInv', '30--21', list(xrange(30,-22,-1))),
    ('PosToPosChunk', '21-30x5', list(xrange(21,31,5))),
    ('NegToPosChunk', '-21-30x5', list(xrange(-21,31,5))),
    ('NegToNegChunk', '-21--30x5', list(xrange(-21,-31,-5))),
    ('PosToNegChunk', '21--30x5', list(xrange(21,-31,-5))),
    ('PosToPosChunkInv', '30-21x5', list(xrange(30,20,-5))),
    ('NegToPosChunkInv', '-30-21x5', list(xrange(-30,22,5))),
    ('NegToNegChunkInv', '-30--21x5', list(xrange(-30,-20,5))),
    ('PosToNegChunkInv', '30--21x5', list(xrange(30,-22,-5))),
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
    ("EmptyString", ""),
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
    ("CommaTrail", "1-20,"),
    ("CommaLead", ",1-20"),
]

class TestFrameSet(unittest.TestCase):
    """
    Exercise the TestFrame object.  Due to the sheer number of permutations, we'll add most tests dynamically.
    """

    def _check___init____frange(self, test, expect):
        """
        Harness to test if the FrameSet.__init__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}")._FrameSet__frange != {0}: got {1}'
        r = f._FrameSet__frange
        self.assertEqual(r, str(test), m.format(test, r))
        m = u'fileseq.FrameSet("{0}")._FrameSet__frange returns {1}: got {2}'
        self.assertIsInstance(r, str, m.format(test, str, type(r)))

    def _check___init____set(self, test, expect):
        """
        Harness to test if the FrameSet.__init__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}")._FrameSet__set != {1}: got {2}'
        r = f._FrameSet__set
        self.assertEqual(r, set(expect), m.format(test, set(expect), r))
        m = u'fileseq.FrameSet("{0}")._FrameSet__set returns {1}: got {2}'
        self.assertIsInstance(r, set, m.format(test, set, type(r)))

    def _check___init____list(self, test, expect):
        """
        Harness to test if the FrameSet.__init__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}")._FrameSet__list != {1}: got {2}'
        r = f._FrameSet__list
        self.assertEqual(r, list(expect), m.format(test, list(expect), r))
        m = u'fileseq.FrameSet("{0}")._FrameSet__list returns {1}: got {2}'
        self.assertIsInstance(r, list, m.format(test, list, type(r)))

    def _check___init____malformed(self, test):
        """
        Harness to test if the FrameSet.__init__ call properly handles malformed strings.
        :param test: the string to pass to FrameSet
        :return: None
        """
        try:
            r = fileseq.FrameSet(test)
        except fileseq.ParseException as err:
            r = err
        except Exception as err:
            r = err
            raise r
        m = u'fileseq.FrameSet("{0}") should fail: got {1}'
        self.assertIsInstance(r, fileseq.ParseException, m.format(test, r))

    def _check___str__(self, test, expect):
        """
        Harness to test if the FrameSet.__str__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'str(fileseq.FrameSet("{0}")) != {0}: got {1}'
        r = str(f)
        self.assertEqual(r, str(test), m.format(test, r))
        m = u'str(fileseq.FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(r, str, m.format(test, str, type(r)))

    def _check___len__(self, test, expect):
        """
        Harness to test if the FrameSet.__len__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'len(fileseq.FrameSet("{0}")) != {1}: got {2}'
        r = len(f)
        self.assertEqual(r, len(expect), m.format(test, len(expect), r))
        m = u'len(fileseq.FrameSet("{0}")) returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check___getitem__(self, test, expect):
        """
        Harness to test if the FrameSet.__getitem__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        i = len(expect) / 2
        m = u'fileseq.FrameSet("{0}")[{1}] != {2}: got {3}'
        try:
            r = f[i]
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[i], m.format(test, i, expect[i], r))
        m = u'fileseq.FrameSet("{0}")[{1}] returns {2}: got {3}'
        self.assertIsInstance(r, int, m.format(test, i, int, type(r)))

    def _check_start(self, test, expect):
        """
        Harness to test if the FrameSet.start call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}").start() != {1}: got {2}'
        try:
            r = f.start()
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[0], m.format(test, expect[0], r))
        m = u'fileseq.FrameSet("{0}").start() returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check_end(self, test, expect):
        """
        Harness to test if the FrameSet.end call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}").end() != {1}: got {2}'
        try:
            r = f.end()
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[-1], m.format(test, expect[-1], r))
        m = u'fileseq.FrameSet("{0}").end() returns {1}: got {2}'
        self.assertIsInstance(r, int, m.format(test, int, type(r)))

    def _check_index(self, test, expect):
        """
        Harness to test if the FrameSet.index call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        i = expect[len(expect)/2]
        m = u'fileseq.FrameSet("{0}").index({1}) != {2}: got {3}'
        try:
            r = f.index(i)
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect.index(i), m.format(test, i, expect.index(i), r))
        m = u'fileseq.FrameSet("{0}").index({1}) returns {2}: got {3}'
        self.assertIsInstance(r, int, m.format(test, i, int, type(r)))

    def _check_frame(self, test, expect):
        """
        Harness to test if the FrameSet.frame call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        i = len(expect)/2
        m = u'fileseq.FrameSet("{0}").frame({1}) != {2}: got {3}'
        try:
            r = f.frame(i)
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect[i], m.format(test, i, expect[i], r))
        m = u'fileseq.FrameSet("{0}").frame({1}) returns {2}: got {3}'
        self.assertIsInstance(r, int, m.format(test, i, int, type(r)))

    def _check_hasFrameTrue(self, test, expect):
        """
        Harness to test if the FrameSet.hasFrame call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        i = max(expect)
        m = u'fileseq.FrameSet("{0}").hasFrame({1}) != {2}: got {3}'
        r = f.hasFrame(i)
        self.assertTrue(r, m.format(test, i, i in expect, r))
        m = u'fileseq.FrameSet("{0}").frame({1}) returns {2}: got {3}'
        self.assertIsInstance(r, bool, m.format(test, i, bool, type(r)))

    def _check_hasFrameFalse(self, test, expect):
        """
        Harness to test if the FrameSet.hasFrame call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        i = max(expect) + 1
        m = u'fileseq.FrameSet("{0}").hasFrame({1}) != {2}: got {3}'
        r = f.hasFrame(i)
        self.assertFalse(r, m.format(test, i, i in expect, r))
        m = u'fileseq.FrameSet("{0}").frame({1}) returns {2}: got {3}'
        self.assertIsInstance(r, bool, m.format(test, i, bool, type(r)))

    def _check___iter__(self, test, expect):
        """
        Harness to test if the FrameSet.__iter__ call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'list(fileseq.FrameSet("{0}")) != {1}: got {2}'
        r = f.__iter__()
        self.assertEqual(list(r), expect, m.format(test, expect, list(r)))
        m = u'fileseq.FrameSet("{0}").end() returns {1}: got {2}'
        self.assertIsInstance(r, types.GeneratorType, m.format(test, types.GeneratorType, type(r)))

    def _check_canSerialize(self, test, expect):
        """
        Harness to test if the FrameSet.__getstate__ and FrameSet.__setstate__ calls allowing pickling.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        f2 = cPickle.loads(cPickle.dumps(f))
        m = u'fileseq.FrameSet("{0}") does not pickle correctly'
        self.assertIsInstance(f2, fileseq.FrameSet, m.format(test))
        self.assertTrue(str(f) == str(f2) and list(f) == list(f2), m.format(test))
        # test old objects being unpickled through new lib
        state = f.__dict__
        f2 = fileseq.FrameSet.__new__(fileseq.FrameSet)
        f2.__setstate__(state)
        self.assertTrue(str(f) == str(f2) and list(f) == list(f2), m.format(test))

    def _check_frameRange(self, test, expect):
        """
        Harness to test if the FrameSet.frameRange call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}").frameRange({1}) != "{2}": got "{3}"'
        p = '((?<![xy:])\d+)'
        l = max([max([len(i) for i in re.findall(p, str(f))]) + 1, 4])
        expect = re.sub(p, lambda m: m.group(0).rjust(l, '0'), str(f))
        try:
            r = f.frameRange(l)
        except Exception as err:
            r = repr(err)
        self.assertEqual(r, expect, m.format(test, l, expect, r))
        m = u'fileseq.FrameSet("{0}").frameRange({1}) returns {2}: got {3}'
        self.assertIsInstance(r, str, m.format(test, i, str, type(r)))

    def _check_invertedFrameRange(self, test, expect):
        """
        Harness to test if the FrameSet.invertedFrameRange call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'fileseq.FrameSet("{0}").invertedFrameRange() != "{1}": got "{2}"'
        r = f.invertedFrameRange()
        t = sorted(f)
        c = sorted(fileseq.FrameSet(r) if r else [])
        self.assertEqual([i for i in xrange(t[0], t[-1]) if i not in t], sorted(c))
        m = u'fileseq.FrameSet("{0}").invertedFrameRange() returns {1}: got {2}'
        self.assertIsInstance(r, str, m.format(test, str, type(r)))

    def _check_normalize(self, test, expect):
        """
        Harness to test if the FrameSet.normalize call works properly.
        :param test: the string to pass to FrameSet
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        f = fileseq.FrameSet(test)
        m = u'set(fileseq.FrameSet("{0}").normalize()) != {1}: got {2}'
        r = f.normalize()
        self.assertEqual(set(f), set(r), m.format(test, set(expect), set(r)))
        m = u'fileseq.FrameSet("{0}").normalize() returns {1}: got {2}'
        self.assertIsInstance(r, fileseq.FrameSet, m.format(test, fileseq.FrameSet, type(r)))

    def _check_isFrameRange(self, test, expect):
        """
        Harness to test if the FrameSet.isFrameRange call works properly.
        :param test: the string to pass to FrameSet.isFrameRange
        :param expect: the expected list of values that FrameSet will hold
        :return: None
        """
        r = fileseq.FrameSet.isFrameRange(test)
        m = u'fileseq.FrameSet.isFrameRange("{0}") != {1}: got {2}'
        self.assertEqual(r, expect, m.format(test, expect, r))
        m = u'fileseq.FrameSet.isFrameRange("{0}") returns {1}: got {2}'
        self.assertIsInstance(r, bool, m.format(test, bool, type(r)))

# due to the sheer number of combinations, we build the bulk of our tests on to TestFrameSet dynamically
for name, tst, exp in FRAME_SET_SHOULD_SUCCEED:

    setattr(
        TestFrameSet, 'testFrameSet%sInitFrange' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___init____frange(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sInitSet' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___init____set(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sInitList' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___init____list(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sStr' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___str__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sLen' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___len__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sGetItem' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___getitem__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sStart' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_start(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sEnd' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_end(self, t, e))
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
        TestFrameSet, 'testFrameSet%sIter' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check___iter__(self, t, e))
    setattr(
        TestFrameSet, 'testFrameSet%sSerialize' % name,
        lambda self, t=tst, e=exp: TestFrameSet._check_canSerialize(self, t, e))
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

    def testSimpleSequence(self):
        self.assertEquals("1-5", fileseq.framesToFrameRange([1,2,3,4,5]))

    def testAdvancedSequence(self):
        self.assertEquals("1-3,6-8,12", fileseq.framesToFrameRange([1,2,3,6,7,8,12]))

    def testAdvancedSequence2(self):
        self.assertEquals("5-15x5,1-5,22", fileseq.framesToFrameRange([5,10,15,1,2,3,4,5,22], sort=False))
        self.assertEquals("1-5,5-15x5,22", fileseq.framesToFrameRange([5,10,15,1,2,3,4,5,22]))

    def testBrokenSequence(self):
        self.assertEquals("2-3,9,12", fileseq.framesToFrameRange([2,3,9,12]))

    def testBrokenSequence2(self):
        self.assertEquals("1-2,4-8", fileseq.framesToFrameRange([1,2,4,5,6,7,8]))

    def testChunkedSequence(self):
        self.assertEquals("5-25x5", fileseq.framesToFrameRange([5,10,15,20,25]))

    def testBrokenChunkedSequence(self):
        self.assertEquals("1-9x2,2-10x2", fileseq.framesToFrameRange([1,3,5,7,9,2,4,6,8,10], sort=False))
        self.assertEquals("1-10", fileseq.framesToFrameRange([1,3,5,7,9,2,4,6,8,10]))

    def testDuplicatedSequence(self):
        self.assertEquals("1-2", fileseq.framesToFrameRange([1,1,1,2,2,2]))
        self.assertEquals("-1,1", fileseq.framesToFrameRange([-1,-1,-1,1,1,1]))

    def testNegativeSimpleSequence(self):
        self.assertEquals("-5-0", fileseq.framesToFrameRange([-5,-4,-3,-2,-1,0]))

    def testOutOfOrderSimpleSequence(self):
        self.assertEquals("1-5", fileseq.framesToFrameRange([2,4,1,2,3,4,5]))

    def testOutOfOrderSimpleSequence(self):
        self.assertEquals("1,10", fileseq.framesToFrameRange([10,1]))
        self.assertEquals("10,1", fileseq.framesToFrameRange([10,1], False))

class TestFileSequence(unittest.TestCase):

    def testSeqGettersType1(self):
        seq = fileseq.FileSequence("/foo/boo.1-5#.exr")
        self.assertEquals(5, len(seq))
        self.assertEquals("/foo/", seq.dirname())
        self.assertEquals("boo.", seq.basename())
        self.assertEquals("#", seq.padding())
        self.assertEquals(".exr", seq.extension())

        self.assertEquals("/foo/boo.9999.exr", seq.frame(9999))
        self.assertEquals("/foo/boo.0001.exr", seq[0])
        self.assertEquals("/foo/boo.0001.exr", seq.index(0))

    def testSeqGettersType2(self):
        seq = fileseq.FileSequence("/foo/boo1-5#.exr")
        self.assertEquals(5, len(seq))
        self.assertEquals("/foo/", seq.dirname())
        self.assertEquals("boo", seq.basename())
        self.assertEquals("#", seq.padding())
        self.assertEquals(".exr", seq.extension())

        self.assertEquals("/foo/boo9999.exr", seq.frame(9999))
        self.assertEquals("/foo/boo0001.exr", seq[0])
        self.assertEquals("/foo/boo0001.exr", seq.index(0))

    def testSetDirname(self):
        seq = fileseq.FileSequence("/foo/bong.1-5@.exr")
        seq.setDirname("/bing/")
        self.assertEquals("/bing/bong.1.exr", seq[0])

    def testSetBasename(self):
        seq = fileseq.FileSequence("/foo/bong.1-5@.exr")
        seq.setBasename("bar.")
        self.assertEquals("/foo/bar.1.exr", seq[0])

    def testSetPadding(self):
        seq = fileseq.FileSequence("/foo/bong.1-5@.exr")
        seq.setPadding("#")
        self.assertEquals("/foo/bong.0001.exr", seq[0])

    def testSetFrameSet(self):
        seq = fileseq.FileSequence("/cheech/chong.1-5#.exr")
        seq.setFrameSet(fileseq.FrameSet("10-20"))
        self.assertEquals("/cheech/chong.10-20#.exr", str(seq))

    def testSetFrameRange(self):
        seq = fileseq.FileSequence("/cheech/chong.1-5#.exr")
        seq.setFrameRange("10-20")
        self.assertEquals("/cheech/chong.10-20#.exr", str(seq))

    def testFrame(self):
        seq = fileseq.FileSequence("/foo/bar/bing.#.exr")
        self.assertEquals("/foo/bar/bing.0001.exr", seq.frame(1))
        self.assertEquals("/foo/bar/bing.#.exr", seq.frame("#"))

    def testIter(self):
        known = set ([
            "/cheech/chong.0001.exr",
            "/cheech/chong.0003.exr",
            "/cheech/chong.0005.exr"
        ])
        seq = fileseq.FileSequence("/cheech/chong.1,3,5#.exr")
        self.assertFalse(known.difference(seq))

    def testFormat(self):
        seq = fileseq.FileSequence("/cheech/chong.1-10,30,40#.exr")
        self.assertEquals("chong.0001-0010,0030,0040#.exr", str(seq.format()))
        self.assertEquals("0011-0029,0031-0039", seq.format("{inverted}"))

        seq = fileseq.findSequencesOnDisk("broken_seq")[0]
        self.assertEquals("0000-0002,0004,0006-0008", seq.format("{range}"))
        self.assertEquals("broke.0000-0002,0004,0006-0008#.exr", seq.format())
        seq = fileseq.findSequencesOnDisk("step_seq")[0]
        self.assertEquals("step_seq/step1.1-13x4,14-17#.exr", str(seq))

    def testSplit(self):
        seqs = fileseq.FileSequence("/cheech/chong.1-10,30,40#.exr").split()
        self.assertEquals("/cheech/chong.0001-0010#.exr", str(seqs[0]))
        self.assertEquals("/cheech/chong.0030#.exr", str(seqs[1]))
        self.assertEquals("/cheech/chong.0040#.exr", str(seqs[2]))

    def testMissingPeriods(self):
        seqs = fileseq.FileSequence("/path/to/something_1-10#_exr")
        self.assertEquals("/path/to/something_0001_exr", seqs.index(0))

    def testNumericFilename(self):
        seqs = fileseq.FileSequence("/path/to/1-10#.exr")
        self.assertEquals("/path/to/0001.exr", seqs.index(0))

    def testNoPlaceholder(self):
        expected = "/path/to/file.mov"
        seqs = fileseq.FileSequence(expected)

        self.assertEquals(expected, seqs.index(0))
        self.assertEquals(expected, seqs.frame(0))
        self.assertEquals(expected, seqs[0])
        self.assertEquals(None, seqs.frameSet())
        self.assertEquals("", seqs.frameRange())
        self.assertEquals("", seqs.invertedFrameRange())
        self.assertEquals(1, len(seqs))

        seqs.setFrameRange("1-100")

        for i in xrange(0,100):
            self.assertEquals(expected, seqs.index(i))
            self.assertEquals(expected, seqs.frame(i+1))
            self.assertEquals(expected, seqs[i])
        self.assertEquals(1, len(seqs))

        seqs.setPadding("#")
        self.assertEquals(100, len(seqs))

    def testSplitXY(self):
        seqs = fileseq.FileSequence("/cheech/0-9x1/chong.1-10#.exr")
        self.assertEquals("/cheech/0-9x1/chong.0001.exr", seqs.index(0))

    def testSerialization(self):
        fs = fileseq.FileSequence("/path/to/file.1-100x2#.exr")
        s = cPickle.dumps(fs, cPickle.HIGHEST_PROTOCOL)
        fs2 = cPickle.loads(s)
        self.assertEquals(str(fs), str(fs2))
        self.assertEquals(len(fs), len(fs2))

class TestFindSequencesOnDisk(unittest.TestCase):

    def testFindSequencesOnDisk(self):
        seqs = fileseq.findSequencesOnDisk("seq")
        self.assertEquals(3, len(seqs))

        known = set([
            "seq/bar1000-1002,1004-1006#.exr",
            "seq/foo.1-5#.exr",
            "seq/foo.1-5#.jpg",
        ])
        found = set([str(s) for s in seqs])
        self.assertFalse(known.difference(found))

    def testNegSequencesOnDisk(self):
        seqs = fileseq.findSequencesOnDisk("seqneg")
        self.assertEquals(1, len(seqs))


    def testFindSequenceOnDiskNegative(self):
        seqs = fileseq.findSequencesOnDisk("seqneg")
        self.assertEquals("seqneg/bar.-1-1#.exr", str(seqs[0]))
        self.assertEquals("seqneg/bar.-001.exr", seqs[0].frame(-1))
        self.assertEquals("seqneg/bar.-1001.exr", seqs[0].frame(-1001))
        self.assertEquals("seqneg/bar.-10011.exr", seqs[0].frame(-10011))
        self.assertEquals("seqneg/bar.1000.exr", seqs[0].frame(1000))

class TestFindSequenceOnDisk(unittest.TestCase):

    def testFindSequenceOnDisk(self):
        tests = [
            ("seq/bar#.exr", "seq/bar1000-1002,1004-1006#.exr"),
            ("seq/foo.#.exr", "seq/foo.1-5#.exr"),
            ("seq/foo.#.jpg", "seq/foo.1-5#.jpg"),
            ("seq/foo.0002.jpg", "seq/foo.1-5#.jpg"),
        ]

        for pattern, expected in tests:
            seq = fileseq.findSequenceOnDisk(pattern)
            self.assertTrue(isinstance(seq, fileseq.FileSequence))
            actual = str(seq)
            self.assertEqual(actual, expected)


class TestPaddingFunctions(unittest.TestCase):
    """
    Test functions that help deal with padding on file sequences.
    """

    def testgetPaddingChars(self):
        """
        Ensure that we're getting back the proper padding characters.
        :return: None
        """
        self.assertEqual(fileseq.getPaddingChars(0), '@')
        self.assertEqual(fileseq.getPaddingChars(1), '@')
        self.assertEqual(fileseq.getPaddingChars(2), '@@')
        self.assertEqual(fileseq.getPaddingChars(3), '@@@')
        self.assertEqual(fileseq.getPaddingChars(4), '#')
        self.assertEqual(fileseq.getPaddingChars(8), '##')

    def testPadFrameRange(self):
        self.assertEqual(fileseq.padFrameRange('1', 6), '000001')
        self.assertEqual(fileseq.padFrameRange('-1', 6), '-000001')
        self.assertEqual(fileseq.padFrameRange('1-100', 6), '000001-000100')
        self.assertEqual(fileseq.padFrameRange('-1-100', 6), '-000001-000100')
        self.assertEqual(fileseq.padFrameRange('-1--100', 6), '-000001--000100')
        self.assertEqual(fileseq.padFrameRange('1--100', 6), '000001--000100')
        self.assertEqual(fileseq.padFrameRange('1-100x2', 6), '000001-000100x2')
        self.assertEqual(fileseq.padFrameRange('-1-100x2', 6), '-000001-000100x2')
        self.assertEqual(fileseq.padFrameRange('-1--100x2', 6), '-000001--000100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 6), '000001--000100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 5), '00001--00100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 4), '0001--0100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 3), '001--100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 2), '01--100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 1), '1--100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', 0), '1--100x2')
        self.assertEqual(fileseq.padFrameRange('1--100x2', -1), '1--100x2')

if __name__ == '__main__':
    unittest.main(verbosity=2)
