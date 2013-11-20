#!/usr/bin/python

import unittest
import sys
import os

TEST_DIR = os.path.abspath(os.path.dirname(__file__))
SRC_DIR = os.path.join(TEST_DIR, "../src")
sys.path.insert(0, SRC_DIR)
os.chdir(TEST_DIR)

import fileseq

class TestFrameSet(unittest.TestCase):
	
	def testContigious(self):
		f = fileseq.FrameSet("1-5")
		self.assertEquals(5, len(f))
		self.assertEquals(1, f[0])
		self.assertEquals(5, f[-1])
		self.assertEquals(5, f[4])
		
		self.assertEquals(f.index(1), 0)
		self.assertEquals(f.index(4), 3)
		self.assertTrue(f.hasFrame(5))
		self.assertFalse(f.hasFrame(6))
		
		# Just try to iterate it to make sure
		# all frames are in the result
		result = frozenset([frame for frame in f])
		for i in range(1, 6):
			self.assertTrue(i in result)
		
	def testCommaSeparated(self):		
		f = fileseq.FrameSet("1-4,8-12")
		self.assertEquals(9, len(f))
		self.assertEquals(1, f[0])
		self.assertEquals(12, f[-1])
		self.assertEquals(12, f[8])
		
	def testChunked(self):		
		fs = fileseq.FrameSet("1-20x5")
		self.assertEquals(4, len(fs))
		expected = [1, 6, 11, 16]
		for e in expected:
			self.assertTrue(fs.hasFrame(e))
	
	def testFilled(self):
		fs = fileseq.FrameSet("1-20y5")
		self.assertEquals(16, len(fs))
		
	def testStaggered(self):
		fs = fileseq.FrameSet("1-20:2")

	def testStaggered(self):
		fs = fileseq.FrameSet("1-20:2")
	
	def testFrame(self):
		fs = fileseq.FrameSet("1-20")
		self.assertEquals(1, fs.frame(0))		

class TestFramesToFrameRange(unittest.TestCase):
	
	def testSimpleSequence(self):
		self.assertEquals("1-5", fileseq.framesToFrameRange([1,2,3,4,5]))
	
	def testBrokenSequence(self):
		self.assertEquals("2,3,9,12", fileseq.framesToFrameRange([2,3,9,12]))

	def testBrokenSequence2(self):
		self.assertEquals("1,2,4-8", fileseq.framesToFrameRange([1,2,4,5,6,7,8]))

	def testChunkedSequence(self):
		self.assertEquals("5-25x5", fileseq.framesToFrameRange([5,10,15,20,25]))

	def testBrokenChunkedSequence(self):
		self.assertEquals("1-9x2,2-10x2", fileseq.framesToFrameRange([1,3,5,7,9,2,4,6,8,10], sort=False))
		self.assertEquals("1-10", fileseq.framesToFrameRange([1,3,5,7,9,2,4,6,8,10]))
	
	def testDuplicatedSequence(self):
		self.assertEquals("1,2", fileseq.framesToFrameRange([1,1,1,2,2,2]))
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

class TestFindSequencesOnDisk(unittest.TestCase):

	def testFindSequencesOnDisk(self):
		seqs = fileseq.findSequencesOnDisk("seq")
		self.assertEquals(2, len(seqs))

		known = set(["seq/bar1000-1002,1004-1006#.exr", "seq/foo.1-5#.exr"])
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
		seq = fileseq.findSequenceOnDisk("seq/bar#.exr")
		self.assertTrue(isinstance(seq, fileseq.FileSequence))
		self.assertEqual(str(seq), "seq/bar1000-1002,1004-1006#.exr")

if __name__ == '__main__':	
	unittest.main(verbosity=2)
