# amara3.util
"""
Some utilities for general use in Amara

Copyright 2008-2015 Uche Ogbuji
"""

def coroutine(func):
    '''
    Decorator: Eliminate the need to call next() to kick-start a co-routine
    From David Beazley: http://www.dabeaz.com/generators/index.html
    '''
    def start(*args,**kwargs):
        coro = func(*args,**kwargs)
        next(coro)
        return coro
    return start


def parse_requirement(r):
    '''
    Parse out package & version from requirements.txt format
    
    For example, might use in setup.py as follows (for requires=REQUIREMENTS, in the setup function):
    
    with open(REQ_FILENAME) as infp:
        #See https://pip.pypa.io/en/stable/reference/pip_install/#requirements-file-format
        reqs = [r.split('#', 1)[0].strip() for r in infp.read().split('\n') if r.split('#', 1)[0].strip() ]
        REQUIREMENTS = [parse_requirement(r) for r in reqs]
    
    >>> from amara3.util import parse_requirement
    >>> reqtxt = """amara3-iri==3.0.0b3
    ... pymarc
    ... rdflib
    ... mmh3
    ... pytest
    ... versa>=0.3.3
    ... 
    ... #From Versa pyreqs.txt
    ... amara3-xml==3.0.0a6
    ... """
    >>> for line in reqtxt.splitlines():
    ...     parse_requirement(line)
    ... 
    'amara3 (==3.0.0b3)'
    'pymarc'
    'rdflib'
    'mmh3'
    'pytest'
    'versa (>=0.3.3)'
    ''
    '#From Versa pyreqs.txt'
    'amara3 (==3.0.0a6)'
    '''
    import re #Defying PEP 8 for perf of other routines
    m = re.search('[<>=][=]', r)
    if m:
        package = r[:m.start()]
        version = r[m.start():]
        if '-' in package:
            package = package.split('-')[0]
        return '{} ({})'.format(package, version)
    else:
        return r


