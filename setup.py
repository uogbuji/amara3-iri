#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Highly recommend installing using `pip install -U .` not `python setup.py install`

Uses pkgutil-style namespace package (Working on figuring out PEP 420)

Note: careful not to conflate install_requires with requirements.txt

https://packaging.python.org/discussions/install-requires-vs-requirements/

Reluctantly use setuptools for now to get install_requires & long_description_content_type

$ python -c "import amara3.version; print(amara3.version.version_info)"
('3', '0', '3')
'''

import sys
from setuptools import setup
#from distutils.core import setup

PROJECT_NAME = 'amara3.iri'
PROJECT_DESCRIPTION = 'Module for handling Internationalized Resource Identifiers (IRIs). Core of the Amara3 project, which offers a variety of data processing tools.',
PROJECT_LICENSE = 'License :: OSI Approved :: Apache Software License'
PROJECT_AUTHOR = 'Uche Ogbuji'
PROJECT_AUTHOR_EMAIL = 'uche@ogbuji.net'
PROJECT_URL = 'https://github.com/uogbuji/amara3-iri'
PACKAGE_DIR = {'amara3': 'pylib'}
PACKAGES = [
    'amara3',
    'amara3.contrib',
]
SCRIPTS = []

CORE_REQUIREMENTS = [
    'pytest',
]

# From http://pypi.python.org/pypi?%3Aaction=list_classifiers
CLASSIFIERS = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        #"Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
]

KEYWORDS=['web', 'data', 'url', 'uri', 'iri']

version_file = 'pylib/version.py'
exec(compile(open(version_file, "rb").read(), version_file, 'exec'), globals(), locals())
__version__ = '.'.join(version_info)

LONGDESC = '''Core of the Amara3 project, which provides a variety of data processing tools. Core is mostly a library for handling Internationalized Resource Identifiers (IRIs)
'''

LONGDESC_CTYPE = 'text/markdown'


setup(
    #namespace_packages=['amara3'],
    name=PROJECT_NAME,
    version=__version__,
    description=PROJECT_DESCRIPTION,
    license=PROJECT_LICENSE,
    author=PROJECT_AUTHOR,
    author_email=PROJECT_AUTHOR_EMAIL,
    #maintainer=PROJECT_MAINTAINER,
    #maintainer_email=PROJECT_MAINTAINER_EMAIL,
    url=PROJECT_URL,
    package_dir=PACKAGE_DIR,
    packages=PACKAGES,
    scripts=SCRIPTS,
    install_requires=CORE_REQUIREMENTS,
    classifiers=CLASSIFIERS,
    long_description=LONGDESC,
    long_description_content_type=LONGDESC_CTYPE,
    keywords=KEYWORDS,
)

