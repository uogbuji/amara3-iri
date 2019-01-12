import pytest
import io, os, sys, inspect #,codecs
import warnings
from amara3 import inputsource, iri
from amara3.iri import IriError
from amara3.inputsource import factory

import os, inspect
def module_path(local_function):
   ''' returns the module path without the use of __file__.  Requires a function defined 
   locally in the module.
   from http://stackoverflow.com/questions/729583/getting-file-path-of-imported-module'''
   return os.path.abspath(inspect.getsourcefile(local_function))

#hack to locate test resource (data) files regardless of from where nose was run
RESOURCEPATH = os.path.normpath(os.path.join(module_path(lambda _: None), '../resource/'))


def test_string_is():
    inp = inputsource('abc')
    assert inp.stream.__class__ == io.StringIO
    assert inp.iri is None
    assert inp.stream.read() == 'abc'


def test_factory_string_is():
    inpl = factory('abc')
    for inp in inpl:
        assert inp.stream.__class__ == io.StringIO
        assert inp.iri is None
        assert inp.stream.read() == 'abc'


def test_stringlist_is():
    inpl = factory(['abc', 'def', 'ghi'])
    inp = inpl[0]
    assert inp.stream.__class__ == io.StringIO
    assert inp.iri is None
    assert inp.stream.read() == 'abc'
    inp = inpl[1]
    assert inp.stream.__class__ == io.StringIO
    assert inp.iri is None
    assert inp.stream.read() == 'def'
    inp = inpl[2]
    assert inp.stream.__class__ == io.StringIO
    assert inp.iri is None
    assert inp.stream.read() == 'ghi'


def test_file_is():
    fname = os.path.join(RESOURCEPATH, 'spam.txt')
    inp = inputsource(open(fname))
    assert inp.iri is None
    assert inp.stream.read() == 'monty\n'


def test_factory_file_is():
    fname = os.path.join(RESOURCEPATH, 'spam.txt')
    inpl = factory(open(fname))
    for inp in inpl:
        assert inp.iri is None
        assert inp.stream.read() == 'monty\n'


def test_stringio_is():
    inp = inputsource(io.StringIO('abc'))
    assert inp.iri is None
    assert inp.stream.read() == 'abc'


def test_bytesio_is():
    inp = inputsource(io.BytesIO('abc'.encode('utf-8')))
    assert inp.iri is None
    assert inp.stream.read() == b'abc'


def test_filelist_is():
    files = [ open(os.path.join(RESOURCEPATH, f)) for f in ('spam.txt', 'eggs.txt') ]
    inpl = factory(files)
    inp = inpl[0]
    assert inp.iri is None
    assert inp.stream.read() == 'monty\n'
    inp = inpl[1]
    assert inp.iri is None
    assert inp.stream.read() == 'python\n'


def test_zip_is():
    zf = open(os.path.join(RESOURCEPATH, 'speggs.zip'), 'rb')
    inpl = factory(zf, zipcheck=True)
    inp = next(inpl)
    assert inp.iri is None
    assert inp.stream.read() == b'python\n'
    inp = next(inpl)
    assert inp.iri is None
    assert inp.stream.read() == b'monty\n'

