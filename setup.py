#!/usr/bin/env python

from distutils.core import setup
#from lib import __version__

versionfile = 'lib/version.py'
exec(compile(open(versionfile, "rb").read(), versionfile, 'exec'), globals(), locals())
__version__ = '.'.join(version_info)

setup(
    name = "amara3-iri",
    version = __version__,
    description="Module for handling Internationalized Resource Identifiers (IRIs). Core of the Amara3 project, which offers a variety of data processing tools.",
    author='Uche Ogbuji',
    author_email='uche@ogbuji.net',
    url='http://uche.ogbuji.net',
    package_dir={'amara3': 'lib'},
    packages=['amara3', 'amara3.contrib'],
    keywords = ["web", "data"],
    #scripts=['exec/exhibit_agg', 'exec/exhibit_lint'],
    classifiers = [
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        #"Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        ],
    long_description = '''The core of the Amara3 project, which contains a variety of data processing tools, is a module for handling Internationalized Resource Identifiers (IRIs)
    '''
    )

