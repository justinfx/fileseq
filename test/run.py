#!/usr/bin/python

import unittest
import sys
sys.path.append("../src")

import fileseq

class TestFrameSet(unittest.TestCase):
	
	def testContigious(self):
		f = fileseq.FrameSet("1-5")
		self.assertEquals(5, len(f))
		self.assertEquals(1, f[0])
		self.assertEquals(5, f[-1])
		self.assertEquals(5, f[4])
		
		self.assertEquals(f.index(4), 5)
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

class TestFramesToFrameRange(unittest.TestCase):
	
	def testSimpleSequence(self):
		self.assertEquals("1-5", fileseq.framesToFrameRange([1,2,3,4,5]))
	
	def testBrokenSequence(self):
		self.assertEquals("2,3,9,12", fileseq.framesToFrameRange([2,3,9,12]))
	
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

if __name__ == '__main__':	
	unittest.main(verbosity=2)
