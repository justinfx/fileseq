#!/usr/bin/env python

import os
from setuptools import setup, find_packages

execfile(os.path.join(os.path.dirname(__file__), "src/fileseq/__version__.py"))

descript = 'A Python library for parsing frame ranges and file ' \
                  'sequences based on a similar library found in Katana.'

setup(name='Fileseq',
      version=__version__,

      package_dir = {'': 'src'},
      packages=find_packages('src'),

      test_suite="test.run",

      author='Matt Chambers',
      author_email='yougotrooted@gmail.com',
      url='https://github.com/sqlboy/fileseq',
      description=descript
     )
