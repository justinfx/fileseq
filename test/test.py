#!/usr/bin/env python

from __future__ import division

import unittest
import cPickle
import re
from itertools import imap
import string

from utils import *

from fileseq import (FrameSet, 
                     FileSequence, 
                     findSequencesOnDisk,
                     findSequenceOnDisk, 
                     padFrameRange, 
                     getPaddingChars, 
                     getPaddingNum, 
                     FileSeqException)

from fileseq import constants, exceptions, utils
from fileseq.constants import PAD_MAP


class TestUtils(unittest.TestCase):
    
    def testXrange(self):
        # Test that a platform-specific xrange does not produce OverflowError
        xrng = utils.xrange(1, sys.maxint)
        self.assertTrue(len(xrng) != 0)


class TestFrameSet(unittest.TestCase):

    def testFloatFrameValues(self):
        table = [
            ([1, 5.8, 10], [1, 5, 10]),
            ([1.5, 5, 10.2], [1, 5, 10]),
            ([1.001, 5, 10.999], [1, 5, 10]),
        ]

        for src, expected in table:
            f = FrameSet(src)
            actual = list(f)
            self.assertEqual(actual, expected)

    def testMaxFrameSize(self):
        _maxSize = constants.MAX_FRAME_SIZE
        try:
            maxSize = constants.MAX_FRAME_SIZE = 500

            # Within range
            utils.xfrange(1, 100, 1, maxSize=-1)
            utils.xfrange(1, 100, 1, maxSize=100)
            FrameSet('1-%d' % maxSize)

            # Should not be allowed
            self.assertRaises(exceptions.MaxSizeException, utils.xfrange, 1, 100, 1, maxSize=50)
            self.assertRaises(exceptions.MaxSizeException, FrameSet, '1-%d' % (maxSize+1))

            # Inverting would produce a huge new range
            fs = FrameSet('1,%d' % (maxSize+3))
            self.assertRaises(exceptions.MaxSizeException, fs.invertedFrameRange)

        finally:
            constants.MAX_FRAME_SIZE = _maxSize

    def test2FramesContiguous(self):
        table = [
            ([1,2], "1-2"),
            ([-1,0], "-1-0"),
            ([-2,-1], "-2--1"),
            ([1,2,5,7,8,10,11], "1-2,5,7-8,10-11"),
            ([-5,-4,-1,1,2,5,7,8,12,13,14,15,16,52,53], "-5--4,-1,1-2,5,7-8,12-16,52-53"),
        ]

        for frames, expected in table:
            fs = FrameSet(frames)
            self.assertEqual(str(fs), expected)

    def testIsConsecutive(self):
        consec = [
            "10-100",
            "-100-100",
            "-100--50",
            "1,2,3,4,5",
            "5,6,7,8,9",
            "-5,-4,-3,-2,-1,0,1",
            "1,2,3,4,3,2,3,4,5,4",
            "-10-3,1-10,5-20,7-30",
            "10--10",
            "10-2,8-0,4--5",
        ]

        nonconsec = [
            "10-20x2",
            "10-20x2,15-30x3",
            "-5-1,3-10",
            "-10-10x2",
            "10--1010x2",
            "1,2,3,4,6,7,8",
            "1,2,3,4,5,0",
            "5,4,3,2,1,6",
        ]

        for t in consec:
            self.assertTrue(FrameSet(t).isConsecutive(), 
                "Expected %s to be consecutive" % t)

        for t in nonconsec:
            self.assertFalse(FrameSet(t).isConsecutive(), 
                "Expected %s to not be consecutive" % t)


class TestBase(unittest.TestCase):

    RX_PATHSEP = re.compile(r'[/\\]')

    def assertEquals(self, a, b):
        # Make sure string paths are compared with normalized
        # path separators
        if isinstance(a, basestring) and isinstance(b, basestring):
            if self.RX_PATHSEP.search(a) and self.RX_PATHSEP.search(b): 
                a = os.path.normpath(a)
                b = os.path.normpath(b)

        super(TestBase, self).assertEquals(a, b)

    def assertEqual(self, a, b):
        self.assertEquals(a, b)
    
    def assertEqualPaths(self, a, b):
        return super(TestBase, self).assertEquals(self.toNormpaths(a), self.toNormpaths(b))
    
    def toNormpaths(self, collection):
        if isinstance(collection, basestring):
            return os.path.normpath(collection)
        return sorted(map(os.path.normpath, collection))
    

class _CustomPathString(str):
    """
    Custom string will always treat substring slices
    as path components, and normalize them by removing
    trailing and duplicate path seps
    """
    @classmethod
    def _create(cls, val):
        if val:
            val = os.path.normpath(str(val))
        return cls(val)

    def __new__(cls, path):
        if path:
            path = os.path.normpath(path)
        return super(_CustomPathString, cls).__new__(cls, path)

    def __add__(self, other):
        return self._create(super(_CustomPathString, self).__add__(other))

    def __getslice__(self, i, j):
        return self._create(super(_CustomPathString, self).__getslice__(i, j))


class TestFileSequence(TestBase):

    def testSeqGettersType1(self):
        seq = FileSequence("/foo/boo.1-5#.exr")
        self.assertEquals(5, len(seq))
        self.assertEquals("/foo/", seq.dirname())
        self.assertEquals("boo.", seq.basename())
        self.assertEquals("#", seq.padding())
        self.assertEquals(".exr", seq.extension())

        self.assertEquals("/foo/boo.9999.exr", seq.frame(9999))
        self.assertEquals("/foo/boo.0001.exr", seq[0])
        self.assertEquals("/foo/boo.0001.exr", seq.index(0))

    def testSeqGettersType2(self):
        seq = FileSequence("/foo/boo1-5#.exr")
        self.assertEquals(5, len(seq))
        self.assertEquals("/foo/", seq.dirname())
        self.assertEquals("boo", seq.basename())
        self.assertEquals("#", seq.padding())
        self.assertEquals(".exr", seq.extension())

        self.assertEquals("/foo/boo9999.exr", seq.frame(9999))
        self.assertEquals("/foo/boo0001.exr", seq[0])
        self.assertEquals("/foo/boo0001.exr", seq.index(0))

    def testSeqGettersPrintf(self):
        seq = FileSequence("/foo/boo.1-5%04d.exr")
        self.assertEquals(5, len(seq))
        self.assertEquals("/foo/", seq.dirname())
        self.assertEquals("boo.", seq.basename())
        self.assertEquals("%04d", seq.padding())
        self.assertEquals(".exr", seq.extension())

        self.assertEquals("/foo/boo.9999.exr", seq.frame(9999))
        self.assertEquals("/foo/boo.0001.exr", seq[0])
        self.assertEquals("/foo/boo.0001.exr", seq.index(0))

    def testSetDirname(self):
        seq = FileSequence("/foo/bong.1-5@.exr")
        seq.setDirname("/bing/")
        self.assertEquals("/bing/bong.1.exr", seq[0])

        seq = FileSequence("/foo/bong.1-5@.exr")
        seq.setDirname("bing")
        self.assertEquals("bing/bong.1.exr", seq[0])

    def testSetBasename(self):
        seq = FileSequence("/foo/bong.1-5@.exr")
        seq.setBasename("bar.")
        self.assertEquals("/foo/bar.1.exr", seq[0])

    def testSetPadding(self):
        seq = FileSequence("/foo/bong.1-5@.exr")
        seq.setPadding("#")
        self.assertEquals("/foo/bong.0001.exr", seq[0])

        seq.setPadding("%02d")
        self.assertEquals("/foo/bong.01.exr", seq[0])

    def testSetFrameSet(self):
        seq = FileSequence("/cheech/chong.1-5#.exr")
        seq.setFrameSet(FrameSet("10-20"))
        self.assertEquals("/cheech/chong.10-20#.exr", str(seq))

    def testSetFrameRange(self):
        seq = FileSequence("/cheech/chong.1-5#.exr")
        seq.setFrameRange("10-20")
        self.assertEquals("/cheech/chong.10-20#.exr", str(seq))

    def testFrame(self):
        seq = FileSequence("/foo/bar/bing.#.exr")
        self.assertEquals("/foo/bar/bing.0001.exr", seq.frame(1))
        self.assertEquals("/foo/bar/bing.#.exr", seq.frame("#"))

        seq = FileSequence("/foo/bar/bing.%04d.exr")
        self.assertEquals("/foo/bar/bing.0001.exr", seq.frame(1))
        self.assertEquals("/foo/bar/bing.%04d.exr", seq.frame("%04d"))

    def testIter(self):
        known = {
            "/cheech/chong.0001.exr",
            "/cheech/chong.0003.exr",
            "/cheech/chong.0005.exr"
        }
        seq = FileSequence("/cheech/chong.1,3,5#.exr")
        self.assertFalse(known.difference(seq))

    def testFormat(self):
        seq = FileSequence("/cheech/chong.1-10,30,40#.exr")
        self.assertEquals("chong.0001-0010,0030,0040#.exr", str(seq.format()))
        self.assertEquals("0011-0029,0031-0039", seq.format("{inverted}"))

        seq = findSequencesOnDisk("broken_seq")[0]
        self.assertEquals("0000-0002,0004,0006-0008", seq.format("{range}"))
        self.assertEquals("broke.0000-0002,0004,0006-0008#.exr", seq.format())
        seq = findSequencesOnDisk("step_seq")[0]
        self.assertEquals("step_seq/step1.1-13x4,14-17#.exr", str(seq))
    
    def testFormatInverted(self):
        _maxSize = constants.MAX_FRAME_SIZE
        try:
            maxSize = constants.MAX_FRAME_SIZE = 500

            # Test catching error for large inverted range
            seq = FileSequence("/path/to/file.1,%d#.ext" % (constants.MAX_FRAME_SIZE+3))
            self.assertRaises(exceptions.MaxSizeException, seq.format, '{inverted}')

        finally:
            constants.MAX_FRAME_SIZE = _maxSize

    def testSplit(self):
        seqs = FileSequence("/cheech/chong.1-10,30,40#.exr").split()
        self.assertEquals("/cheech/chong.0001-0010#.exr", str(seqs[0]))
        self.assertEquals("/cheech/chong.0030#.exr", str(seqs[1]))
        self.assertEquals("/cheech/chong.0040#.exr", str(seqs[2]))

    def testMissingPeriods(self):
        seqs = FileSequence("/path/to/something_1-10#_exr")
        self.assertEquals("/path/to/something_0001_exr", seqs.index(0))

        seqs = FileSequence("/path/to/something_1-10%04d_exr")
        self.assertEquals("/path/to/something_0001_exr", seqs.index(0))

    def testNumericFilename(self):
        seqs = FileSequence("/path/to/1-10#.exr")
        self.assertEquals("/path/to/0001.exr", seqs.index(0))

        seqs = FileSequence("/path/to/1-10%04d.exr")
        self.assertEquals("/path/to/0001.exr", seqs.index(0))

    def testNoPlaceholder(self):
        expected = "/path/to/file.mov"
        seqs = FileSequence(expected)

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

    def testNoPlaceholderNumExt(self):
        basename = 'file'
        exts = ('.7zip', '.mp4')

        for ext in exts:
            expected = basename + ext
            seqs = FileSequence(expected)

            self.assertEquals(ext, seqs.extension())
            self.assertEquals(basename, seqs.basename())
            self.assertEquals(expected, str(seqs))

    def testSplitXY(self):
        seqs = FileSequence("/cheech/0-9x1/chong.1-10#.exr")
        self.assertEquals("/cheech/0-9x1/chong.0001.exr", seqs.index(0))

    def testSerialization(self):
        fs = FileSequence("/path/to/file.1-100x2#.exr")
        s = cPickle.dumps(fs, cPickle.HIGHEST_PROTOCOL)
        fs2 = cPickle.loads(s)
        self.assertEquals(str(fs), str(fs2))
        self.assertEquals(len(fs), len(fs2))

        fs = FileSequence("/path/to/file.1-100x2%04d.exr")
        s = cPickle.dumps(fs, cPickle.HIGHEST_PROTOCOL)
        fs2 = cPickle.loads(s)
        self.assertEquals(str(fs), str(fs2))
        self.assertEquals(len(fs), len(fs2))

    def testHasVersionNoFrame(self):
        fs = FileSequence("/path/to/file_v2.exr")
        self.assertEquals(fs.start(), 0)
        self.assertEquals(fs.end(), 0)
        self.assertEquals(fs.padding(), '')
        self.assertEquals(fs.extension(), '.exr')
        self.assertEquals(str(fs), "/path/to/file_v2.exr")

    def testHasFrameNoVersion(self):
        fs = FileSequence("/path/to/file.2.exr")
        self.assertEquals(fs.start(), 2)
        self.assertEquals(fs.end(), 2)
        self.assertEquals(fs.padding(), '@')
        self.assertEquals(fs.extension(), '.exr')
        self.assertEquals(str(fs), "/path/to/file.2@.exr")

    def testNoFrameNoVersionNoExt(self):
        fs = FileSequence("/path/to/file")
        self.assertEquals(fs.start(), 0)
        self.assertEquals(fs.end(), 0)
        self.assertEquals(fs.padding(), '')
        self.assertEquals(fs.dirname(), '/path/to/')
        self.assertEquals(fs.basename(), 'file')
        self.assertEquals(fs.extension(), '')
        self.assertEquals(str(fs), "/path/to/file")

        fs = FileSequence("file")
        self.assertEquals(fs.start(), 0)
        self.assertEquals(fs.end(), 0)
        self.assertEquals(fs.padding(), '')
        self.assertEquals(fs.dirname(), '')
        self.assertEquals(fs.basename(), 'file')
        self.assertEquals(fs.extension(), '')
        self.assertEquals(str(fs), "file")

    def testEmptyBasename(self):
        seq = FileSequence("/path/to/1-5#.exr")
        self.assertEquals(seq.basename(), "")
        self.assertEquals(len(seq), 5)
        self.assertEquals(seq.padding(), '#')

        seq = FileSequence("/path/to/1-5%04d.exr")
        self.assertEquals(seq.basename(), "")
        self.assertEquals(len(seq), 5)
        self.assertEquals(seq.padding(), '%04d')

    def ringSubclasses(self):
        sep = lambda p: p.replace("/", os.sep)
        tests = [
            ("/path/to/files.0001.ext", sep("/path/to/"), "files."),
            ("/path/to/files.1-100#.ext", sep("/path/to/"), "files."),
            ("/path/to/files.ext", sep("/path/to/"), "files"),
            ("/path/to/files", sep("/path/to/"), "files"),
        ]
        for path, dirname, basename in tests:
            fs = FileSequence(_CustomPathString(path))
            self.assertTrue(fs.dirname() == dirname, "Expected '%s', got '%s' (with %s)" % (dirname, fs.dirname(), path))
            self.assertTrue(fs.basename() == basename, "Expected '%s', got '%s' (with %s)" % (basename, fs.basename(), path))

    def test_yield_sequences_in_list(self):
        paths = [
            '/path/to/file20.v123.5.png',
            '/path/to/file20.v123.1.exr',
            '/path/to/file20.v123.2.exr',
            '/path/to/file20.v123.3.exr',
            '/path/to/.cruft.file',
            '/path/to/.cruft',
            '/path/to/file2.exr',
            '/path/to/file2.7zip',
            '/path/to/file.2.7zip',
            '/path/to/file.3.7zip',
            '/path/to/file.4.7zip',
            '/path/to/file.4.mp4',
            '', # empty path test
            "mixed_seqs/file5.ext",
            "mixed_seqs/file20.ext",
            "mixed_seqs/file30.ext",
            "mixed_seqs/no_ext",
            "mixed_seqs/no_ext.200,300@@@",
            "mixed_seqs/no_ext_10",
            "mixed_seqs/not_a_seq.ext",
            "mixed_seqs/seq.0001.ext",
            "mixed_seqs/seq.0002.ext",
            "mixed_seqs/seq.0003.ext",
            "mixed_seqs/seq2a.1.ext",
            "mixed_seqs/seq2a.2.ext",
            "mixed_seqs/seq2a.3.ext",
            "/path/to/file4-4.exr",
            "/path/to/file4-5.exr",
            "/path/to/file--4.exr",
            "path/01.exr",
            "path/02.exr",
            "path/03.exr",
            "path/001.file",
            "path/002.file",
            "path/003.file",
            "path/0001.jpg",
            "path/0002.jpg",
            "path/0003.jpg",
            "2frames.01.jpg",
            "2frames.02.jpg",
            '8frames.01.jpg',
            '8frames.02.jpg',
            '8frames.05.jpg',
            '8frames.07.jpg',
            '8frames.08.jpg',
            '8frames.10.jpg',
            '8frames.11.jpg',
        ]

        expected = {
            '/path/to/file2@.7zip',
            '/path/to/file20.v123.1-3@.exr',
            '/path/to/file.2-4@.7zip',
            '/path/to/file2@.exr',
            '/path/to/file.4@.mp4',
            '/path/to/.cruft.file',
            '/path/to/.cruft',
            '/path/to/file20.v123.5@.png',
            "mixed_seqs/file5,20,30@.ext",
            "mixed_seqs/seq2a.1-3@.ext",
            "mixed_seqs/seq.1-3#.ext",
            "mixed_seqs/not_a_seq.ext",
            "mixed_seqs/no_ext",
            "mixed_seqs/no_ext_10@@",
            "mixed_seqs/no_ext.200,300@@@",
            '/path/to/file4-5--4@@.exr',
            '/path/to/file--4@@.exr',
            'path/1-3@@.exr',
            'path/1-3@@@.file',
            'path/1-3#.jpg',
            '2frames.1-2@@.jpg',
            '8frames.1-2,5,7-8,10-11@@.jpg',
        }

        actual = set(str(fs) for fs in FileSequence.yield_sequences_in_list(paths))
        self.assertEquals(actual, expected)

        paths = imap(_CustomPathString, paths)
        actual = set(str(fs) for fs in FileSequence.yield_sequences_in_list(paths))
        self.assertEquals(actual, {str(_CustomPathString(p)) for p in expected})

    def testIgnoreFrameSetStrings(self):
        for char in "xy:,".split():
            fs = FileSequence("/path/to/file{0}1-1x1#.exr".format(char))
            self.assertEquals(fs.basename(), "file{0}".format(char))
            self.assertEquals(fs.start(), 1)
            self.assertEquals(fs.end(), 1)
            self.assertEquals(fs.padding(), '#')
            self.assertEquals(str(fs), "/path/to/file{0}1-1x1#.exr".format(char))


class TestFindSequencesOnDisk(TestBase):

    def testFindSequencesOnDisk(self):
        seqs = findSequencesOnDisk("seq")
        self.assertEquals(6, len(seqs))

        known = {
            "seq/bar1000-1002,1004-1006#.exr",
            "seq/foo.1-5#.exr",
            "seq/foo.1-5#.jpg",
            "seq/foo.debug.1-5#.exr",
            "seq/foo_1#.exr",
            "seq/1-3#.exr",
        }
        found = set([str(s) for s in seqs])
        self.assertEqualPaths(found, known)

    def testNegSequencesOnDisk(self):
        seqs = findSequencesOnDisk("seqneg")
        self.assertEquals(1, len(seqs))

    def testFindSequenceOnDiskNegative(self):
        seqs = findSequencesOnDisk("seqneg")
        self.assertEquals("seqneg/bar.-1-1#.exr", str(seqs[0]))
        self.assertEquals("seqneg/bar.-001.exr", seqs[0].frame(-1))
        self.assertEquals("seqneg/bar.-1001.exr", seqs[0].frame(-1001))
        self.assertEquals("seqneg/bar.-10011.exr", seqs[0].frame(-10011))
        self.assertEquals("seqneg/bar.1000.exr", seqs[0].frame(1000))

    def testFindSequencesOnDiskSkipHiddenFiles(self):
        seqs = findSequencesOnDisk("seqhidden")
        self.assertEquals(3, len(seqs))

        known = set(self.toNormpaths([
            "seqhidden/bar1000-1002,1004-1006#.exr",
            "seqhidden/foo.1-5#.exr",
            "seqhidden/foo.1-5#.jpg",
        ]))
        found = set(self.toNormpaths([str(s) for s in seqs]))
        self.assertEqual(known, found)
        self.assertFalse(known.difference(found))

    def testFindSequencesOnDiskIncludeHiddenFiles(self):
        seqs = findSequencesOnDisk("seqhidden", include_hidden=True)
        self.assertEquals(7, len(seqs))

        known = {
            "seqhidden/bar1000-1002,1004-1006#.exr",
            "seqhidden/.bar1000-1002,1004-1006#.exr",
            "seqhidden/foo.1-5#.exr",
            "seqhidden/.foo.1-5#.exr",
            "seqhidden/foo.1-5#.jpg",
            "seqhidden/.foo.1-5#.jpg",
            "seqhidden/.hidden",
        }
        found = set([str(s) for s in seqs])
        self.assertEqualPaths(known, found)

    def testCrossPlatformPathSep(self):
        expected = {
            "seqsubdirs/sub1/1-3#.exr",
            "seqsubdirs/sub1/bar1000-1002,1004-1006#.exr",
            "seqsubdirs/sub1/foo.1-5#.exr",
            "seqsubdirs/sub1/foo.1-5#.jpg",
            "seqsubdirs/sub1/foo.debug.1-5#.exr",
            "seqsubdirs/sub1/foo_1#.exr",
        }

        import ntpath 
        _join = os.path.join
        os.path.join = ntpath.join

        try:
            self.assertEqual(os.path.join('a', 'b'), 'a\\b')
            seqs = findSequencesOnDisk("seqsubdirs/sub1")

            self.assertEquals(len(expected), len(seqs))

            actual = set(str(s) for s in seqs)
            self.assertEqual(actual, expected)

        finally:
            os.path.join = _join

class TestFindSequenceOnDisk(TestBase):

    def testFindSequenceOnDisk(self):
        tests = [
            ("seq/bar#.exr", "seq/bar1000-1002,1004-1006#.exr"),
            ("seq/foo.#.exr", "seq/foo.1-5#.exr"),
            ("seq/foo.#.jpg", "seq/foo.1-5#.jpg"),
            ("seq/foo.0002.jpg", "seq/foo.1-5#.jpg"),
            ("seq/foo.#.exr", "seq/foo.1-5#.exr"),
            ("seq/foo.debug.#.exr", "seq/foo.debug.1-5#.exr"),
            ("seq/#.exr", "seq/1-3#.exr"),
            ("seq/bar1001.exr", "seq/bar1001.exr"),
            ("seq/foo_0001.exr", "seq/foo_0001.exr"),
        ]

        for pattern, expected in tests:
            seq = findSequenceOnDisk(pattern)
            self.assertTrue(isinstance(seq, FileSequence))
            actual = str(seq)
            self.assertEqual(actual, expected)

    def testCrossPlatformPathSep(self):
        tests = [
            ("seq/bar#.exr", "seq\\bar1000-1002,1004-1006#.exr"),
            ("seq/foo.#.exr", "seq\\foo.1-5#.exr"),
            ("seq/foo.#.jpg", "seq\\foo.1-5#.jpg"),
            ("seq/foo.0002.jpg", "seq\\foo.1-5#.jpg"),
            ("seq/foo.#.exr", "seq\\foo.1-5#.exr"),
            ("seq/foo.debug.#.exr", "seq\\foo.debug.1-5#.exr"),
            ("seq/#.exr", "seq\\1-3#.exr"),
            ("seq/bar1001.exr", "seq/bar1001.exr"),
            ("seq/foo_0001.exr", "seq/foo_0001.exr"),
        ]

        import ntpath 
        _path = os.path
        os.path = ntpath

        try:
            self.assertEqual(os.path.join('a', 'b'), 'a\\b')

            for pattern, expected in tests:
                seq = findSequenceOnDisk(pattern)
                self.assertTrue(isinstance(seq, FileSequence))
                actual = str(seq)
                self.assertEqual(actual, expected) 

        finally:
            os.path = _path

    def testPaddingMatch(self):
        tests = [
            ("mixed/seq.#.ext", "mixed/seq.-1-5#.ext"),
            ("mixed/seq.@@.ext", "mixed/seq.-1-5@@.ext"),
            ("mixed/seq.@@@@@.ext", "mixed/seq.-1-5@@@@@.ext"),
            ("mixed/seq.@.ext", None),
            ("mixed/seq.%04d.ext", "mixed/seq.-1-5#.ext"),
            ("mixed/seq.%02d.ext", "mixed/seq.-1-5@@.ext"),
            ("mixed/seq.%05d.ext", "mixed/seq.-1-5@@@@@.ext"),
            ("mixed/seq.%01d.ext", None),
        ]

        for pattern, expected in tests:
            if expected is None:
                with self.assertRaises(FileSeqException):
                    findSequenceOnDisk(pattern, strictPadding=True)
                continue
            
            seq = findSequenceOnDisk(pattern, strictPadding=True)
            self.assertTrue(isinstance(seq, FileSequence))
            
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
        self.assertEqual(getPaddingChars(0), '@')
        self.assertEqual(getPaddingChars(1), '@')
        self.assertEqual(getPaddingChars(2), '@@')
        self.assertEqual(getPaddingChars(3), '@@@')
        self.assertEqual(getPaddingChars(4), '#')
        self.assertEqual(getPaddingChars(8), '##')

    def testgetPaddingNum(self):
        """
        Ensure that we're getting back the proper padding number.
        :return: None
        """
        self.assertEqual(getPaddingNum('@'), 1)
        self.assertEqual(getPaddingNum('@@'), 2)
        self.assertEqual(getPaddingNum('@@@'), 3)
        self.assertEqual(getPaddingNum('#'), 4)
        self.assertEqual(getPaddingNum('##'), 8)
        self.assertEqual(getPaddingNum('#@'), 5)
        self.assertEqual(getPaddingNum('##@@'), 10)

        self.assertEqual(getPaddingNum('%01d'), 1)
        self.assertEqual(getPaddingNum('%1d'), 1)
        self.assertEqual(getPaddingNum('%04d'), 4)
        self.assertEqual(getPaddingNum('%10d'), 10)

        allPossibleChars = [s for s in string.printable if s not in PAD_MAP.keys()]
        for char in allPossibleChars:
            self.assertRaises(ValueError, getPaddingNum, char)
            self.assertRaises(ValueError, getPaddingNum, '#{}'.format(char))
            self.assertRaises(ValueError, getPaddingNum, '@{}'.format(char))

        allPossibleChars = [s for s in string.printable if s not in PAD_MAP.keys() and s not in string.digits]
        for char in allPossibleChars:
            self.assertRaises(ValueError, getPaddingNum, '%{}d'.format(char))

    def testPadFrameRange(self):
        self.assertEqual(padFrameRange('1', 6), '000001')
        self.assertEqual(padFrameRange('-1', 6), '-000001')
        self.assertEqual(padFrameRange('1-100', 6), '000001-000100')
        self.assertEqual(padFrameRange('-1-100', 6), '-000001-000100')
        self.assertEqual(padFrameRange('-1--100', 6), '-000001--000100')
        self.assertEqual(padFrameRange('1--100', 6), '000001--000100')
        self.assertEqual(padFrameRange('1-100x2', 6), '000001-000100x2')
        self.assertEqual(padFrameRange('-1-100x2', 6), '-000001-000100x2')
        self.assertEqual(padFrameRange('-1--100x2', 6), '-000001--000100x2')
        self.assertEqual(padFrameRange('1--100x2', 6), '000001--000100x2')
        self.assertEqual(padFrameRange('1--100x2', 5), '00001--00100x2')
        self.assertEqual(padFrameRange('1--100x2', 4), '0001--0100x2')
        self.assertEqual(padFrameRange('1--100x2', 3), '001--100x2')
        self.assertEqual(padFrameRange('1--100x2', 2), '01--100x2')
        self.assertEqual(padFrameRange('1--100x2', 1), '1--100x2')
        self.assertEqual(padFrameRange('1--100x2', 0), '1--100x2')
        self.assertEqual(padFrameRange('1--100x2', -1), '1--100x2')


if __name__ == '__main__':
    unittest.main(verbosity=1)
