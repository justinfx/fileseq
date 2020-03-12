#!/usr/bin/env python

from __future__ import absolute_import
import os
from setuptools import setup, find_packages
from codecs import open

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "src/fileseq/__version__.py")) as version_file:
    exec(version_file.read())

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()
    
descript = 'A Python library for parsing frame ranges and file sequences ' \
           'commonly used in VFX and Animation applications.'

setup(name='Fileseq',
      version=__version__,

      package_dir = {'': 'src'},
      packages=find_packages('src'),

      test_suite="test.run",

      author='Matt Chambers',
      author_email='yougotrooted@gmail.com',

      maintainer='Justin Israel',
      maintainer_email='justinisrael@gmail.com',

      url='https://github.com/justinfx/fileseq',

      description=descript,
      long_description=long_description,
      long_description_content_type="text/markdown",

      license='MIT',

      classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3',
      ],

      keywords='vfx visual effects file sequence frames image',

      install_requires=['future'],
      )
