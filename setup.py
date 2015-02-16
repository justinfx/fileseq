#!/usr/bin/env python

from setuptools import setup, find_packages


descript = 'A Python library for parsing frame ranges and file ' \
                  'sequences based on a similar library found in Katana.'

setup(name='Fileseq',
      version='1.0.0',

      package_dir = {'': 'src'},
      packages=find_packages('src'),

      test_suite="test.run",

      author='Matt Chambers',
      author_email='yougotrooted@gmail.com',
      url='https://github.com/sqlboy/fileseq',
      description=descript
     )
