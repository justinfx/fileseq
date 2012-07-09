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
		print fs.normalize()
				
if __name__ == '__main__':
	unittest.main(verbosity=2)
