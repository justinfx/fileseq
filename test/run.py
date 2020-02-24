#!/usr/bin/env python

from __future__ import absolute_import

import os
import sys
import unittest

if __name__ == '__main__':
    testsuite = unittest.TestLoader().discover(os.path.dirname(__file__))
    result = unittest.TextTestRunner(verbosity=1).run(testsuite)
    sys.exit(not result.wasSuccessful())
