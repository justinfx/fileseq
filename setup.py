#!/usr/bin/env python

import os
from setuptools import setup, find_packages
from codecs import open

here = os.path.abspath(os.path.dirname(__file__))

execfile(os.path.join(here, "src/fileseq/__version__.py"))

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
    
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
      
      description=descript,
      long_description=long_description,
      
      license='MIT',

      classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
      ],
      
      keywords='vfx visual effects file sequence frames image',
     )
