# amara3.inputsource
"""
Utilities for managing data inputs for Amara

Copyright 2008-2015 Uche Ogbuji
"""

import zipfile
import functools
from enum import Enum
from io import StringIO, BytesIO

from amara3 import iri
from urllib.request import urlopen

class inputsourcetype(Enum):
    unknown = 0
    stream = 1
    string = 2
    iri = 3
    filename = 4
    zipfilestream = 5


def factory(obj, defaultsourcetype=inputsourcetype.unknown, encoding=None, streamopenmode='rb', zipcheck=False):
    '''
    Helper function to create an iterable of inputsources from compound sources such as a zip file
    Returns an iterable of input sources

    obj - object, possibly list or tuple of items to be converted into one or more inputsource
    '''
    if isinstance(obj, inputsource):
        return obj
    _inputsource = functools.partial(inputsource, encoding=encoding, streamopenmode=streamopenmode)
    if isinstance(obj, tuple) or isinstance(obj, list):
        inputsources = [ _inputsource(o, sourcetype=defaultsourcetype) for o in obj ]
    #if isinstance(objs, str) or isinstance(objs, bytes) or isinstance(objs, bytearray):
    #Don't do a zipcheck unless we know we can rewind the obj
    #Because zipfile.is_zipfile fast forwards to EOF
    elif zipcheck and hasattr(obj, 'seek'):
        inputsources = []
        if zipfile.is_zipfile(obj):
            def zipfilegen():
                zf = zipfile.ZipFile(obj, 'r') #Mode must be r, w or a
                for info in zf.infolist():
                    #From the doc: Note If the ZipFile was created by passing in a file-like object as the first argument to the constructor, then the object returned by open() shares the ZipFile’s file pointer. Under these circumstances, the object returned by open() should not be used after any additional operations are performed on the ZipFile object.
                    yield(_inputsource(zf.open(info, mode='r')))
            inputsources = zipfilegen()
        else:
            #Because zipfile.is_zipfile fast forwards to EOF
            obj.seek(0, 0)
    else:
        inputsources = [_inputsource(obj)]
    return inputsources


class inputsource(object):
    '''
    A flexible class for managing input sources for e.g. XML processing

    Loosely based on Amara's old inputsource <https://github.com/zepheira/amara/blob/master/lib/lib/_inputsource.py>
    '''
    def __init__(self, obj, siri=None, encoding=None, streamopenmode='rb',
                    sourcetype=inputsourcetype.unknown):
        '''
        obj - byte string, proper string (only if you really know what you're doing),
            file-like object (stream), file path or URI.
        uri - optional override URI.  Base URI for the input source will be set to
            this value

        >>> from amara3 import inputsource
        >>> inp = inputsource('abc')
        >>> inp.stream
        <_io.StringIO object at 0x1056fbf78>
        >>> inp.iri
        >>> print(inp.iri)
        None
        >>> inp = inputsource(['abc', 'def']) #Now multiple streams in one source
        >>> inp.stream
        <_io.StringIO object at 0x1011aff78>
        >>> print(inp.iri)
        None
        >>> inp = next(inp)
        >>> inp.stream
        <_io.StringIO object at 0x1011af5e8>
        >>> print(inp.iri)
        None
        >>>
        '''
        # from amara3 import inputsource; inp = inputsource('foo.zip')
        # from amara3 import inputsource; inp = inputsource('test/resource/std-examples.zip')
        # s = inp.stream.read(100)
        # s
        # b'<?xml version="1.0" encoding="UTF-8"?>\r\n<!-- edited with XML Spy v4.3 U (http://www.xmlspy.com) by M'
        # s
        # b'<?xml version="1.0" encoding="UTF-8"?>\r\n<collection xmlns="http://www.loc.gov/MARC21/slim">\r\n  <reco'

        self.stream = None
        self.iri = siri
        self.sourcetype = sourcetype

        if obj in ('', b''):
            raise ValueError("Cannot parse an empty string as XML")

        if hasattr(obj, 'read'):
            #Create dummy Uri to use as base
            #uri = uri or uuid4().urn
            self.stream = obj
        #elif sourcetype == inputsourcetype.xmlstring:
            #See this article about XML detection heuristics
            #http://www.xml.com/pub/a/2007/02/28/what-does-xml-smell-like.html
            #uri = uri or uuid4().urn
        elif self.sourcetype == inputsourcetype.iri or (siri and iri.matches_uri_syntax(obj)):
            self.iri = siri or obj
            self.stream = urlopen(iri)
        elif self.sourcetype == inputsourcetype.filename or (siri and iri.is_absolute(obj) and not os.path.isfile(obj)):
            #FIXME: convert path to URI
            self.iri = siri or iri.os_path_to_uri(obj)
            self.stream = open(obj, streamopenmode)
        elif self.sourcetype == inputsourcetype.string or isinstance(obj, str) or isinstance(obj, bytes):
            self.stream = StringIO(obj)
            #If obj is beyond a certain length, don't even try it as a URI
            #if len(obj) < MAX_URI_LENGTH_FOR_HEURISTIC:
            #    self.iri = iri.os_path_to_uri(obj)
            #    self.stream = urlopen(siri)
        else:
            raise ValueError("Unable to recognize as an inputsource")
        return

    @staticmethod
    def text(obj, siri=None, encoding=None):
        '''
        Set up an input source from text, according to the markup convention of the term
        (i.e. in Python terms a string with XML, HTML, fragments thereof, or tag soup)

        Helps with processing content sources that are not unambiguously XML or HTML strings
        (e.g. could be mistaken for filenames or IRIs)
        '''
        return inputsource(obj, siri, encoding, sourcetype=inputsourcetype.string)
