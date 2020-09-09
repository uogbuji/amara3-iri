"""
Various IRI utilities
"""

import os, sys
import io
import urllib, urllib.request
import email
from email.utils import formatdate as _formatdate

__all__ = ['iriref', 'iridict', 'codex']

from . import iri

class iriref(str):
    '''
    IRI reference object, mostly a string that smart about
    IRI stem/tail abbreviations (as made famous by XML namespaces)

    >>> from amara3.iri import I
    >>> I('spam')
    'spam'
    >>> I('spam eggs')
    [raises ValueError]
    '''
    def __new__(cls, value):
        if not iri.matches_uri_ref_syntax(value):
            raise ValueError(_('Invalid IRI reference: "{0}"'.format(value)))
        self = super(iriref, cls).__new__(cls, value)
        #self = unicode, cls).__new__(cls, value)
        # optionally do stuff to self here
        return self

    def __repr__(self):
        return u'I(' + str(self) + ')'

    def __call__(self, tail):
        '''
        >>> from versa import I
        >>> base = I('https://example.org/')
        >>> a = base('a')
        >>> a
        I(https://example.org/a)
        '''
        # Just dumb concatenation for now
        return iriref(str(self) + str(tail))

I = iriref


class codex:
    '''
    Proposed helper IRI stem registry for speeding up IRI comparisons

    HOWEVER: Not enough evidence yet of significant enough improvement for the added complexity. Some observations on Python 3.8.5 on MacOS:

    python -m timeit -s "i1 = 'http://example.org/spam'; i2 = 'http://example.org/eggs';" "i1 == i2; i1 == i1"

    5000000 loops, best of 5: 39.5 nsec per loop

    python -m timeit -s "i1 = (1, 'spam'); i2 = (1, 'eggs');" "i1 == i2; i1 == i1"

    5000000 loops, best of 5: 47.6 nsec per loop

    Indicates that using a base IRI / tail tuple would make perf *worse*

    python -m timeit -s "i1 = '1:spam'; i2 = '1:eggs';" "i1 == i2; i1 == i1"

    10000000 loops, best of 5: 35.4 nsec per loop

    Some improvement with an inline prefix to shorten the string, but really worth it?...

    '''
    pass


# FIXME: Port to use UserDict
class iridict(dict):
    """
    Dictionary that uses IRIs as keys, attempting some degree of IRI (URI)
    equivalence as defined in RFC 3986 section 6. If IRIs A and B match
    after normalization they wlll lead to identical dictionary behaviors.
    This covers cases such as
    "http://spam/~x/" <--> "http://spam/%7Ex/" <--> "http://spam/%7ex"
    (viz RFC 3986)
    and "file:///x" <--> "file://localhost/x"
    (viz RFC 1738).
    It also covers case normalization on the scheme, percent-encoded octets,
    percent-encoding normalization (decoding of octets corresponding to
    unreserved characters).
    """
    # RFC 3986 requires localhost to be the default host no matter
    # what the scheme, but, being descriptive of existing practices,
    # leaves it up to the implementation to decide whether to use this
    # and other tests of URI equivalence in the determination of
    # same-document references. So our implementation results in what
    # is arguably desirable, but not strictly required, behavior.
    #
    #FIXME: make localhost the default for all schemes, not just file
    def _normalizekey(self, key):
        key = normalize_case(normalize_percent_encoding(key))
        if key[:17] == 'file://localhost/':
            return 'file://' + key[16:]
        else:
            return key

    def __getitem__(self, key):
        return super(uridict, self).__getitem__(self._normalizekey(key))

    def __setitem__(self, key, value):
        return super(uridict, self).__setitem__(self._normalizekey(key), value)

    def __delitem__(self, key):
        return super(uridict, self).__delitem__(self._normalizekey(key))

    def has_key(self, key):
        return super(uridict, self).has_key(self._normalizekey(key))

    def __contains__(self, key):
        return super(uridict, self).__contains__(self._normalizekey(key))

    def __iter__(self):
        return iter(self.keys())

    iterkeys = __iter__
    def iteritems(self):
        for key in self.iterkeys():
            yield key, self.__getitem__(key)


#FIXME: Port to more amara.lib.iri functions
def get_filename_from_url(url):
    fullname = url.split('/')[-1].split('#')[0].split('?')[0]
    return fullname


def get_filename_parts_from_url(url):
    fullname = url.split('/')[-1].split('#')[0].split('?')[0]
    t = list(os.path.splitext(fullname))
    if t[1]:
        t[1] = t[1][1:]
    return t
