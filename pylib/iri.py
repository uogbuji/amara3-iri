"""
Classes and functions related to IRI/URI processing, validation, resolution, etc.

Copyright 2008-2020 Uche Ogbuji and Mike Brown
"""

__all__ = [
  'IriError',
  'I',

  # IRI tools
  "iri_to_uri",
  "nfc_normalize",
  "convert_ireg_name",

  # RFC 3986 implementation
  'matches_uri_ref_syntax', 'matches_uri_syntax',
  'percent_encode', 'percent_decode',
  'split_uri_ref', 'unsplit_uri_ref',
  'split_authority', 'split_fragment',
  'absolutize', 'relativize', 'remove_dot_segments',
  'normalize_case', 'normalize_percent_encoding',
  'normalize_path_segments', 'normalize_path_segments_in_uri',

  # RFC 3151 implementation
  'urn_to_public_id', 'public_id_to_urn',

  # Miscellaneous
  'is_absolute', 'get_scheme', 'strip_fragment',
  'os_path_to_uri', 'uri_to_os_path', 'basejoin', 'join',
  'WINDOWS_SLASH_COMPAT', 'path_resolve',
]

import os, sys
import urllib, urllib.request
import re, io
import email
from string import ascii_letters
from email.utils import formatdate as _formatdate
from uuid import UUID, uuid1, uuid4

from .irihelper import I

# whether os_path_to_uri should treat "/" same as "\" in a Windows path
WINDOWS_SLASH_COMPAT = True

DEFAULT_HIERARCHICAL_SEP = '/'

PERCENT_DECODE_BYTES = ('0123456789%s-._~' % ascii_letters).encode('ascii')

class IriError(Exception):
    """
    Exception related to URI/IRI processing
    """
    pass
    #FIXME: Re-incorporate the exception details below
'''
        return {
            IriError.INVALID_BASE_URI: _(
                "Invalid base URI: %(base)r cannot be used to resolve "
                " reference %(ref)r"),
            IriError.RELATIVE_BASE_URI: _(
                "Invalid base URI: %(base)r cannot be used to resolve "
                "reference %(ref)r; the base URI must be absolute, not "
                "relative."),
            IriError.NON_FILE_URI: _(
                "Only a 'file' URI can be converted to an OS-specific path; "
                "URI given was %(uri)r"),
            IriError.UNIX_REMOTE_HOST_FILE_URI: _(
                "A URI containing a remote host name cannot be converted to a "
                " path on posix; URI given was %(uri)r"),
            IriError.RESOURCE_ERROR: _(
                "Error retrieving resource %(loc)r: %(msg)s"),
            IriError.UNSUPPORTED_PLATFORM: _(
                "Platform %(platform)r not supported by URI function "
                "%(function)s"),
            IriError.SCHEME_REQUIRED: _(
                "Scheme-based resolution requires a URI with a scheme; "
                "neither the base URI %(base)r nor the reference %(ref)r "
                "have one."),
            IriError.INVALID_PUBLIC_ID_URN: _(
                "A public ID cannot be derived from URN %(urn)r "
                "because it does not conform to RFC 3151."),
            IriError.UNSUPPORTED_SCHEME: _(
                "The URI scheme %(scheme)s is not supported by resolver "),
            IriError.DENIED_BY_RULE: _(
                "Access to IRI %(uri)r was denied by action of an IRI restriction"),
            }
'''


def iri_to_uri(iri, convertHost=False):
    r"""
    Converts an IRI or IRI reference to a URI or URI reference,
    implementing sec. 3.1 of draft-duerst-iri-10.

    The convertHost flag indicates whether to perform conversion of
    the ireg-name (host) component of the IRI to an RFC 2396-compatible
    URI reg-name (IDNA encoded), e.g.
    iri_to_uri('http://r\xe9sum\xe9.example.org/', convertHost=False)
    => 'http://r%C3%A9sum%C3%A9.example.org/'
    iri_to_uri('http://r\xe9sum\xe9.example.org/', convertHost=True)
    => 'http://xn--rsum-bpad.example.org/'

    Ordinarily, the IRI should be given as a unicode string. If the IRI
    is instead given as a byte string, then it will be assumed to be
    UTF-8 encoded, will be decoded accordingly, and as per the
    requirements of the conversion algorithm, will NOT be normalized.
    """
    if not isinstance(iri, str):
        iri = nfc_normalize(iri)

    # first we have to get the host
    (scheme, auth, path, query, frag) = split_uri_ref(iri)
    if auth and auth.find('@') > -1:
        userinfo, hostport = auth.split('@')
    else:
        userinfo = None
        hostport = auth
    if hostport and hostport.find(':') > -1:
        host, port = hostport.split(':')
    else:
        host = hostport
        port = None
    if host:
        host = convert_ireg_name(host)
        auth = ''
        if userinfo:
            auth += userinfo + '@'
        auth += host
        if port:
            auth += ':' + port
    iri = unsplit_uri_ref((scheme, auth, path, query, frag))

    res = ''
    pos = 0
    #FIXME: use re.subn with substitution function for big speed-up
    surrogate = None
    for c in iri:
        cp = ord(c)
        if cp > 128:
            if cp < 160:
                # FIXME: i18n
                raise ValueError(_("Illegal character at position %d (0-based) of IRI %r" % (pos, iri)))
            # 'for c in iri' may give us surrogate pairs
            elif cp > 55295:
                if cp < 56320:
                    # d800-dbff
                    surrogate = c
                    continue
                elif cp < 57344:
                    # dc00-dfff
                    if surrogate is None:
                        raise ValueError(_("Illegal surrogate pair in %r" % iri))
                    c = surrogate + c
                else:
                    raise ValueError(_("Illegal surrogate pair in %r" % iri))
                surrogate = None
            for octet in c.encode('utf-8'):
                res += '%%%02X' % ord(octet)
        else:
            res += c
        pos += 1
    return res


def nfc_normalize(iri):
    """
    Normalizes the given unicode string according to Unicode Normalization Form C (NFC)
    so that it can be used as an IRI or IRI reference.
    """
    from unicodedata import normalize
    return normalize('NFC', iri)


def convert_ireg_name(iregname):
    """
    Converts the given ireg-name component of an IRI to a string suitable for use
    as a URI reg-name in pre-rfc2396bis schemes and resolvers. Returns the ireg-name
    """
    # I have not yet verified that the default IDNA encoding
    # matches the algorithm required by the IRI spec, but it
    # does work on the one simple example in the spec.
    return iregname.encode('idna').decode('ascii')


#=============================================================================
# Functions that implement aspects of RFC 3986
#
_validation_setup_completed = False
def _init_uri_validation_regex():
    """
    Called internally to compile the regular expressions needed by
    URI validation functions, just once, the first time a function
    that needs them is called.
    """
    global _validation_setup_completed
    if _validation_setup_completed:
        return

    #-------------------------------------------------------------------------
    # Regular expressions for determining the non-URI-ness of strings
    #
    # A given string's designation as a URI or URI reference comes from the
    # context in which it is being used, not from its syntax; a regular
    # expression can at most only determine whether a given string COULD be a
    # URI or URI reference, based on its lexical structure.
    #
    # 1. Altova's regex (in the public domain; courtesy Altova)
    #
    # # based on the BNF grammar in the original RFC 2396
    # ALTOVA_REGEX = r"(([a-zA-Z][0-9a-zA-Z+\-\.]*:)?/{0,2}" + \
    #                r"[0-9a-zA-Z;/?:@&=+$\.\-_!~*'()%]+)?" + \
    #                r"(#[0-9a-zA-Z;/?:@&=+$\.\-_!~*'()%]+)?"
    #
    # This regex matches URI references, and thus URIs as well. It is also
    # lenient; some strings that are not URI references can falsely match.
    #
    # It is also not very useful as-is, because it essentially has the form
    # (group1)?(group2)? -- this matches the empty string, and in fact any
    # string or substring can be said to match this pattern. To be useful,
    # this regex (and any like it) must be changed so that it only matches
    # an entire string. This is accomplished in Python by using the \A and \Z
    # delimiters around the pattern:
    #
    # BETTER_ALTOVA_REGEX = r"\A(?!\n)%s\Z" % ALTOVA_REGEX
    #
    # The (?!\n) takes care of an edge case where a string consisting of a
    # sole linefeed character would falsely match.
    #
    # 2. Python regular expressions for strict validation of URIs and URI
    #    references (in the public domain; courtesy Fourthought, Inc.)
    #
    # Note that we do not use any \d or \w shortcuts, as these are
    # potentially locale or Unicode sensitive.
    #
    # # based on the ABNF in RFC 3986,
    # # "Uniform Resource Identifier (URI): Generic Syntax"
    pchar           = r"(?:[0-9A-Za-z\-_\.!~*'();:@&=+$,]|(?:%[0-9A-Fa-f]{2}))"
    fragment        = r"(?:[0-9A-Za-z\-_\.!~*'();:@&=+$,/?]|(?:%[0-9A-Fa-f]{2}))*"
    query           = fragment
    segment_nz_nc   = r"(?:[0-9A-Za-z\-_\.!~*'();@&=+$,]|(?:%[0-9A-Fa-f]{2}))+"
    segment_nz      = r'%s+' % pchar
    segment         = r'%s*' % pchar
    #path_empty      = r''  # zero characters
    path_rootless   = r'%s(?:/%s)*' % (segment_nz, segment)   # begins with a segment
    path_noscheme   = r'%s(?:/%s)*' % (segment_nz_nc, segment)  # begins with a non-colon segment
    path_absolute   = r'/(?:%s)?' % path_rootless  # begins with "/" but not "//"
    path_abempty    = r'(?:/%s)*' % segment   # begins with "/" or is empty
    #path            = r'(?:(?:%s)|(?:%s)|(?:%s)|(?:%s))?' % (path_abempty, path_absolute, path_noscheme, path_rootless)
    domainlabel     = r'[0-9A-Za-z](?:[0-9A-Za-z\-]{0,61}[0-9A-Za-z])?'
    qualified       = r'(?:\.%s)*\.?' % domainlabel
    reg_name        = r"(?:(?:[0-9A-Za-z\-_\.!~*'();&=+$,]|(?:%[0-9A-Fa-f]{2}))*)"
    dec_octet       = r'(?:[0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])'
    IPv4address     = r'(?:%s\.){3}(?:%s)' % (dec_octet, dec_octet)
    h16             = r'[0-9A-Fa-f]{1,4}'
    ls32            = r'(?:(?:%s:%s)|%s)' % (h16, h16, IPv4address)
    IPv6address     = r'(?:' + \
                      r'(?:(?:%s:){6}%s)' % (h16, ls32) + \
                      r'|(?:::(?:%s:){5}%s)' % (h16, ls32) + \
                      r'|(?:%s?::(?:%s:){4}%s)' % (h16, h16, ls32) + \
                      r'|(?:(?:(?:%s:)?%s)?::(?:%s:){3}%s)' % (h16, h16, h16, ls32) + \
                      r'|(?:(?:(?:%s:)?%s){0,2}::(?:%s:){2}%s)' % (h16, h16, h16, ls32) + \
                      r'|(?:(?:(?:%s:)?%s){0,3}::%s:%s)' % (h16, h16, h16, ls32) + \
                      r'|(?:(?:(?:%s:)?%s){0,4}::%s)' % (h16, h16, ls32) + \
                      r'|(?:(?:(?:%s:)?%s){0,5}::%s)' % (h16, h16, h16) + \
                      r'|(?:(?:(?:%s:)?%s){0,6}::)' % (h16, h16) + \
                      r')'
    IPvFuture       = r"(?:v[0-9A-Fa-f]+\.[0-9A-Za-z\-\._~!$&'()*+,;=:]+)"
    IP_literal      = r'\[(?:%s|%s)\]' % (IPv6address, IPvFuture)
    port            = r'[0-9]*'
    host            = r'(?:%s|%s|%s)?' % (IP_literal, IPv4address, reg_name)
    userinfo        = r"(?:[0-9A-Za-z\-_\.!~*'();:@&=+$,]|(?:%[0-9A-Fa-f]{2}))*"
    authority       = r'(?:%s@)?%s(?::%s)?' % (userinfo, host, port)
    scheme          = r'[A-Za-z][0-9A-Za-z+\-\.]*'
    #absolute_URI    = r'%s:%s(?:\?%s)?' % (scheme, hier_part, query)
    relative_part   = r'(?:(?://%s%s)|(?:%s)|(?:%s))?' % (authority, path_abempty,
                                                          path_absolute, path_noscheme)
    relative_ref    = r'%s(?:\?%s)?(?:#%s)?' % (relative_part, query, fragment)
    hier_part       = r'(?:(?://%s%s)|(?:%s)|(?:%s))?' % (authority, path_abempty,
                                                          path_absolute, path_rootless)
    URI             = r'%s:%s(?:\?%s)?(?:#%s)?' % (scheme, hier_part, query, fragment)
    URI_reference   = r'(?:%s|%s)' % (URI, relative_ref)

    STRICT_URI_PYREGEX = r"\A%s\Z" % URI
    STRICT_URIREF_PYREGEX = r"\A(?!\n)%s\Z" % URI_reference

    global URI_PATTERN, URI_REF_PATTERN
    URI_PATTERN = re.compile(STRICT_URI_PYREGEX)        # strict checking for URIs
    URI_REF_PATTERN = re.compile(STRICT_URIREF_PYREGEX) # strict checking for URI refs
    _validation_setup_completed = True
    return


def matches_uri_ref_syntax(s):
    """
    This function returns true if the given string could be a URI reference,
    as defined in RFC 3986, just based on the string's syntax.

    A URI reference can be a URI or certain portions of one, including the
    empty string, and it can have a fragment component.
    """
    if not _validation_setup_completed:
        _init_uri_validation_regex()
    return URI_REF_PATTERN.match(s) is not None


def matches_uri_syntax(s):
    """
    This function returns true if the given string could be a URI, as defined
    in RFC 3986, just based on the string's syntax.

    A URI is by definition absolute (begins with a scheme) and does not end
    with a #fragment. It also must adhere to various other syntax rules.
    """
    if not _validation_setup_completed:
        _init_uri_validation_regex()
    return URI_PATTERN.match(s) is not None


_split_uri_ref_setup_completed = False
def _init_split_uri_ref_pattern():
    """
    Called internally to compile the regular expression used by
    split_uri_ref() just once, the first time the function is called.
    """
    global _split_uri_ref_setup_completed
    if _split_uri_ref_setup_completed:
        return

    # Like the others, this regex is also in the public domain.
    # It is based on this one, from RFC 3986 appendix B
    # (unchanged from RFC 2396 appendix B):
    # ^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?
    regex = r"^(?:(?P<scheme>[^:/?#]+):)?(?://(?P<authority>[^/?#]*))?(?P<path>[^?#]*)(?:\?(?P<query>[^#]*))?(?:#(?P<fragment>.*))?$"
    global SPLIT_URI_REF_PATTERN
    SPLIT_URI_REF_PATTERN = re.compile(regex)
    _split_uri_ref_setup_completed = True
    return


def split_uri_ref(iri_ref):
    """
    Given a valid URI reference as a string, returns a tuple representing the
    generic URI components, as per RFC 3986 appendix B. The tuple's structure
    is (scheme, authority, path, query, fragment).

    All values will be strings (possibly empty) or None if undefined.

    Note that per RFC 3986, there is no distinction between a path and
    an "opaque part", as there was in RFC 2396.
    """
    if not _split_uri_ref_setup_completed:
        _init_split_uri_ref_pattern()
    # the pattern will match every possible string, so it's safe to
    # assume there's a groupdict method to call.
    g = SPLIT_URI_REF_PATTERN.match(iri_ref).groupdict()
    scheme      = g['scheme']
    authority   = g['authority']
    path        = g['path']
    query       = g['query']
    fragment    = g['fragment']
    return (scheme, authority, path, query, fragment)


def unsplit_uri_ref(iri_refSeq):
    """
    Given a sequence as would be produced by split_uri_ref(), assembles and
    returns a URI reference as a string.
    """
    if not isinstance(iri_refSeq, (tuple, list)):
        raise TypeError(_("sequence expected, got %s" % type(iri_refSeq)))
    (scheme, authority, path, query, fragment) = iri_refSeq
    uri = ''
    if scheme is not None:
        uri += scheme + ':'
    if authority is not None:
        uri += '//' + authority
    uri += path
    if query is not None:
        uri += '?' + query
    if fragment is not None:
        uri += '#' + fragment
    return uri


_split_authority_setup_completed = False
def _init_split_authority_pattern():
    """
    Called internally to compile the regular expression used by
    split_authority() just once, the first time the function is called.
    """
    global _split_authority_setup_completed
    if _split_authority_setup_completed:
        return
    global SPLIT_AUTHORITY_PATTERN
    regex = r'(?:(?P<userinfo>[^@]*)@)?(?P<host>[^:]*)(?::(?P<port>.*))?'
    SPLIT_AUTHORITY_PATTERN = re.compile(regex)
    _split_authority_setup_completed = True
    return


def split_authority(authority):
    """
    Given a string representing the authority component of a URI, returns
    a tuple consisting of the subcomponents (userinfo, host, port). No
    percent-decoding is performed.
    """
    if not _split_authority_setup_completed:
        _init_split_authority_pattern()
    m = SPLIT_AUTHORITY_PATTERN.match(authority)
    if m:
        return m.groups()
    else:
        return (None, authority, None)


def split_fragment(uri):
    """
    Given a URI or URI reference, returns a tuple consisting of
    (base, fragment), where base is the portion before the '#' that
    precedes the fragment component.
    """
    # The only '#' in a legit URI will be the fragment separator,
    # but in the wild, people get sloppy. Assume the last '#' is it.
    pos = uri.rfind('#')
    if pos == -1:
        return (uri, uri[:0])
    else:
        return (uri[:pos], uri[pos+1:])


# "unreserved" characters are allowed in a URI, and do not have special
# meaning as delimiters of URI components or subcomponents. They may
# appear raw or percent-encoded, but percent-encoding is discouraged.
# This set of characters is sufficiently long enough that using a
# compiled regex is faster than using a string with the "in" operator.
#UNRESERVED_PATTERN = re.compile(r"[0-9A-Za-z\-\._~!*'()]") # RFC 2396
UNRESERVED_PATTERN = re.compile(r'[0-9A-Za-z\-\._~]') # RFC 3986

# "reserved" characters are allowed in a URI, but they may or always do
# have special meaning as delimiters of URI components or subcomponents.
# When being used as delimiters, they must be raw, and when not being
# used as delimiters, they must be percent-encoded.
# This set of characters is sufficiently short enough that using a
# string with the "in" operator is faster than using a compiled regex.
# The characters in the string are ordered according to how likely they
# are to be found (approximately), for faster operation with "in".
#RESERVED = "/&=+?;@,:$[]" # RFC 2396 + RFC 2732
RESERVED = "/=&+?#;@,:$!*[]()'" # RFC 3986


def percent_encode(s, encoding='utf-8', encodeReserved=True, spaceToPlus=False,
                     nlChars=None, reservedChars=RESERVED):
    """
    [*** Experimental API ***] This function applies percent-encoding, as
    described in RFC 3986 sec. 2.1, to the given string, in order to prepare
    the string for use in a URI. It replaces characters that are not allowed
    in a URI. By default, it also replaces characters in the reserved set,
    which normally includes the generic URI component delimiters ":" "/"
    "?" \"#\" "[" "]" "@" and the subcomponent delimiters "!" "$" "&" "\'" "("
    ")" "*" "+" "," ";" "=".

    Ideally, this function should be used on individual components or
    subcomponents of a URI prior to assembly of the complete URI, not
    afterward, because this function has no way of knowing which characters
    in the reserved set are being used for their reserved purpose and which
    are part of the data. By default it assumes that they are all being used
    as data, thus they all become percent-encoded.

    The characters in the reserved set can be overridden from the default by
    setting the reservedChars argument. The percent-encoding of characters
    in the reserved set can be disabled by unsetting the encodeReserved flag.
    Do this if the string is an already-assembled URI or a URI component,
    such as a complete path.

    The encoding argument will be used to determine the percent-encoded octets
    for characters that are not in the U+0000 to U+007F range. The codec
    identified by the encoding argument must return a byte string.

    The spaceToPlus flag controls whether space characters are changed to
    "+" characters in the result, rather than being percent-encoded.
    Generally, this is not required, and given the status of "+" as a
    reserved character, is often undesirable. But it is required in certain
    situations, such as when generating application/x-www-form-urlencoded
    content or RFC 3151 public identifier URNs, so it is supported here.

    The nlChars argument, if given, is a sequence type in which each member
    is a substring that indicates a "new line". Occurrences of this substring
    will be replaced by '%0D%0A' in the result, as is required when generating
    application/x-www-form-urlencoded content.

    This function is similar to urllib.quote(), but is more conformant and
    Unicode-friendly. Suggestions for improvements welcome.

    >>> from amara3 import iri
    >>> iri.percent_encode('http://bibfra.me/vocab/relation/論定')
    http%3A%2F%2Fbibfra.me%2Fvocab%2Frelation%2F%E8%AB%96%E5%AE%9A
    """
    res = ''
    if nlChars is not None:
        for c in nlChars:
            s.replace(c, '\r\n')
    #FIXME: use re.subn with substitution function for big speed-up
    for c in s:
        # surrogates? -> percent-encode according to given encoding
        if UNRESERVED_PATTERN.match(c) is None:
            cp = ord(c)
            # ASCII range?
            if cp < 128:
                # space? -> plus if desired
                if spaceToPlus and c == ' ':
                    res += '+'
                # reserved? -> percent-encode if desired
                elif c in reservedChars:
                    if encodeReserved:
                        res += '%%%02X' % cp
                    else:
                        res += c
                # not unreserved or reserved, so percent-encode
                # FIXME: should percent-encode according to given encoding;
                # ASCII range is not special!
                else:
                    res += '%%%02X' % cp
            # non-ASCII-range unicode?
            else:
                # percent-encode according to given encoding
                for octet in c.encode(encoding):
                    res += '%%%02X' % octet

        # unreserved -> safe to use as-is
        else:
            res += c
    return res

_ASCII_PAT = re.compile('([\x00-\x7f]+)')

_HEXDIG = '0123456789ABCDEFabcdef'
_HEXTOBYTE = None


def _unquote_to_bytes(s, decodable=None):
    """_unquote_to_bytes('abc%20def') -> b'abc def'."""
    # Note: strings are encoded as UTF-8. This is only an issue if it contains
    # unescaped non-ASCII characters, which URIs should not.
    if not s:
        # Is it a string-like object?
        s.split
        return b''
    if isinstance(s, str):
        s = s.encode('utf-8')
    bits = s.split(b'%')
    if len(bits) == 1:
        return s
    res = [bits[0]]
    append = res.append
    # Delay the initialization of the table to not waste memory
    # if the function is never called
    global _HEXTOBYTE
    if _HEXTOBYTE is None:
        _HEXTOBYTE = {(a + b).encode(): bytes([int(a + b, 16)])
                      for a in _HEXDIG for b in _HEXDIG}
    for item in bits[1:]:
        try:
            c = chr(int(item[:2], 16)).encode('ascii')
            if decodable is None or c in decodable:
                append(_HEXTOBYTE[item[:2]])
                append(item[2:])
            #FIXME: We'll need to do our own surrogate pair decoding because:
            #>>> '\ud800'.encode('utf-8') -> UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' in position 0: surrogates not allowed
            else:
                append(b'%')
                append(item)
        except (ValueError, KeyError):
            append(b'%')
            append(item)
    return b''.join(res)

#>>> from amara3.iri import percent_decode
#>>> u0 = 'example://A/b/c/%7bfoo%7d'
#>>> u1 = percent_decode(u0)
#>>> u1
#'example://A/b/c/{foo}'


def percent_decode(s, encoding='utf-8', decodable=None, errors='replace'):
    """
    [*** Experimental API ***] Reverses the percent-encoding of the given
    string.

    Similar to urllib.parse.unquote()

    By default, all percent-encoded sequences are decoded, but if a byte
    string is given via the 'decodable' argument, only the sequences
    corresponding to those octets will be decoded.

    Percent-encoded sequences are converted to bytes, then converted back to
    string (Unicode) according to the given encoding.
    For example, by default, 'abc%E2%80%A2' will be converted to 'abc\u2022',
    because byte sequence E2 80 A2 represents character U+2022 in UTF-8.

    This function is intended for use on the portions of a URI that are
    delimited by reserved characters (see percent_encode), or on a value from
    data of media type application/x-www-form-urlencoded.

    >>> from amara3.iri import percent_decode
    >>> u0 = 'http://host/abc%E2%80%A2/x/y/z'
    >>> u1 = percent_decode(u0)
    >>> hex(ord(u1[15]))
    '0x2022'
    """
    # Most of this comes from urllib.parse.unquote().
    # Note: strings are encoded as UTF-8. This is only an issue if it contains
    # unescaped non-ASCII characters, which URIs should not.
    # If given a string argument, does not decode
    # percent-encoded octets above %7F.

    if '%' not in s:
        #s.split
        return s
    if encoding is None:
        encoding = 'utf-8'
    if errors is None:
        errors = 'replace'
    bits = _ASCII_PAT.split(s)
    res = [bits[0]]
    append = res.append #Saving the func lookups in the tight loop below
    for i in range(1, len(bits), 2):
        append(_unquote_to_bytes(bits[i], decodable=decodable).decode(encoding, errors))
        append(bits[i + 1])
    return ''.join(res)


def absolutize(iri_ref, base_iri, limit_schemes=None):
    """
    Resolves a IRI reference to absolute form, effecting the result of RFC
    3986 section 5. The IRI reference is considered to be relative to the
    given base IRI.

    iri_ref - relative URI to be resolved into absolute form. If already
    absolute, it will be returned as is.

    base_iri - base IRI for resolving iri_ref. If '' or None iri_ref will be
    returned as is. base_iri should matche the absolute-URI syntax rule of
    RFC 3986, and its path component should not contain '.' or '..' segments
    if the scheme is hierarchical. If these are violated you may get unexpected
    results.

    This function only conducts a minimal sanity check in order to determine
    if relative resolution is possible: it raises a ValueError if the base
    URI does not have a scheme component. While it is true that the base URI
    is irrelevant if the URI reference has a scheme, an exception is raised
    in order to signal that the given string does not even come close to
    meeting the criteria to be usable as a base URI.

    It is the caller's responsibility to make a determination of whether the
    URI reference constitutes a "same-document reference", as defined in RFC
    2396 or RFC 3986. As per the spec, dereferencing a same-document
    reference "should not" involve retrieval of a new representation of the
    referenced resource. Note that the two specs have different definitions
    of same-document reference: RFC 2396 says it is *only* the cases where the
    reference is the empty string, or \"#\" followed by a fragment; RFC 3986
    requires making a comparison of the base URI to the absolute form of the
    reference (as is returned by the spec), minus its fragment component,
    if any.

    This function is similar to urlparse.urljoin() and urllib.basejoin().
    Those functions, however, are (as of Python 2.3) outdated, buggy, and/or
    designed to produce results acceptable for use with other core Python
    libraries, rather than being earnest implementations of the relevant
    specs. Their problems are most noticeable in their handling of
    same-document references and 'file:' URIs, both being situations that
    come up far too often to consider the functions reliable enough for
    general use.
    """
    # Reasons to avoid using urllib.basejoin() and urlparse.urljoin():
    # - Both are partial implementations of long-obsolete specs.
    # - Both accept relative URLs as the base, which no spec allows.
    # - urllib.basejoin() mishandles the '' and '..' references.
    # - If the base URL uses a non-hierarchical or relative path,
    #    or if the URL scheme is unrecognized, the result is not
    #    always as expected (partly due to issues in RFC 1808).
    # - If the authority component of a 'file' URI is empty,
    #    the authority component is removed altogether. If it was
    #    not present, an empty authority component is in the result.
    # - '.' and '..' segments are not always collapsed as well as they
    #    should be (partly due to issues in RFC 1808).
    # - Effective Python 2.4, urllib.basejoin() *is* urlparse.urljoin(),
    #    but urlparse.urljoin() is still based on RFC 1808.

    # This procedure is based on the pseudocode in RFC 3986 sec. 5.2.
    #
    # ensure base URI is absolute
    if not base_iri or is_absolute(iri_ref):
        return iri_ref
    if not base_iri or not is_absolute(base_iri):
        raise ValueError("Invalid base URI: {base} cannot be used to resolve "
                "reference {ref}; the base URI must be absolute, not "
                "relative.".format(base=base_iri, ref=iri_ref))
    if limit_schemes and get_scheme(base_iri) not in limit_schemes:
        scheme = get_scheme(base_iri)
        raise ValueError("The URI scheme {scheme} is not supported by resolver".format(scheme=scheme))

    # shortcut for the simplest same-document reference cases
    if iri_ref == '' or iri_ref[0] == '#':
        return base_iri.split('#')[0] + iri_ref
    # ensure a clean slate
    tScheme = tAuth = tPath = tQuery = None
    # parse the reference into its components
    (rScheme, rAuth, rPath, rQuery, rFrag) = split_uri_ref(iri_ref)
    # if the reference is absolute, eliminate '.' and '..' path segments
    # and skip to the end
    if rScheme is not None:
        tScheme = rScheme
        tAuth = rAuth
        tPath = remove_dot_segments(rPath)
        tQuery = rQuery
    else:
        # the base URI's scheme, and possibly more, will be inherited
        (bScheme, bAuth, bPath, bQuery, bFrag) = split_uri_ref(base_iri)
        # if the reference is a net-path, just eliminate '.' and '..' path
        # segments; no other changes needed.
        if rAuth is not None:
            tAuth = rAuth
            tPath = remove_dot_segments(rPath)
            tQuery = rQuery
        # if it's not a net-path, we need to inherit pieces of the base URI
        else:
            # use base URI's path if the reference's path is empty
            if not rPath:
                tPath = bPath
                # use the reference's query, if any, or else the base URI's,
                tQuery = rQuery is not None and rQuery or bQuery
            # the reference's path is not empty
            else:
                # just use the reference's path if it's absolute
                if rPath[0] == '/':
                    tPath = remove_dot_segments(rPath)
                # merge the reference's relative path with the base URI's path
                else:
                    if bAuth is not None and not bPath:
                        tPath = '/' + rPath
                    else:
                        tPath = bPath[:bPath.rfind('/')+1] + rPath
                    tPath = remove_dot_segments(tPath)
                # use the reference's query
                tQuery = rQuery
            # since the reference isn't a net-path,
            # use the authority from the base URI
            tAuth = bAuth
        # inherit the scheme from the base URI
        tScheme = bScheme
    # always use the reference's fragment (but no need to define another var)
    #tFrag = rFrag

    # now compose the target URI (RFC 3986 sec. 5.3)
    return unsplit_uri_ref((tScheme, tAuth, tPath, tQuery, rFrag))


def relativize(targetUri, againstUri, subPathOnly=False):
    """
    This method returns a relative URI that is consistent with `targetURI`
    when resolved against `againstUri`.  If no such relative URI exists, for
    whatever reason, this method returns `None`.

    To be precise, if a string called `rel` exists such that
    ``absolutize(rel, againstUri) == targetUri``, then `rel` is returned by
    this function.  In these cases, `relativize` is in a sense the inverse
    of `absolutize`.  In all other cases, `relativize` returns `None`.

    The following idiom may be useful for obtaining compliant relative
    reference strings (e.g. for `path`) for use in other methods of this
    package::

      path = relativize(os_path_to_uri(path), os_path_to_uri('.'))

    If `subPathOnly` is `True`, then this method will only return a relative
    reference if such a reference exists relative to the last hierarchical
    segment of `againstUri`.  In particular, this relative reference will
    not start with '/' or '../'.
    """

    # We might want to change the semantics slightly to allow a relative
    # target URI to be a valid "relative path" (and just return it).  For
    # now, though, absolute URIs only.
    if not is_absolute(targetUri) or not is_absolute(againstUri):
        return None

    targetUri = normalize_path_segments_in_uri(targetUri)
    againstUri = normalize_path_segments_in_uri(againstUri)

    splitTarget = list(split_uri_ref(absolutize(targetUri, targetUri)))
    splitAgainst = list(split_uri_ref(absolutize(againstUri, againstUri)))

    if not splitTarget[:2] == splitAgainst[:2]:
        return None

    subPathSplit = [None, None] + splitTarget[2:]

    targetPath = splitTarget[2]
    againstPath = splitAgainst[2] or '/'

    leadingSlash = False
    if targetPath[:1] == '/' or againstPath[:1] == '/':
        if targetPath[:1] == againstPath[:1]:
            targetPath = targetPath[1:]
            againstPath = againstPath[1:]
            leadingSlash = True
        else:
            return None

    targetPathSegments = targetPath.split('/')
    againstPathSegments = againstPath.split('/')

    # Count the number of path segments in common.
    i = 0
    while True:
        # Stop if we get to the end of either segment list.
        if not(len(targetPathSegments) > i and
               len(againstPathSegments) > i):
            break

        # Increment the count when the lists agree, unless we are at the
        # last segment of either list and that segment is an empty segment.
        # We bail on this case because an empty ending segment in one path
        # must not match a mid-path empty segment in the other.
        if (targetPathSegments[i] == againstPathSegments[i]
            and not (i + 1 == len(againstPathSegments) and
                     '' == againstPathSegments[i])
            and not (i + 1 == len(targetPathSegments) and
                     '' == targetPathSegments[i])):
            i = i + 1
        # Otherwise stop.
        else:
            break

    # The target path has `i` segments in common with the basis path, and
    # the last segment (after the final '/') doesn't matter; we'll need to
    # traverse the rest.
    traverse = len(againstPathSegments) - i - 1

    relativePath = None
    # If the two paths do not agree on any segments, we have two special
    # cases.
    if i == 0 and leadingSlash:
        # First, if the ruling path only had one segment, then our result
        # can be a relative path.
        if len(againstPathSegments) == 1:
            relativePath = targetPath
        # Otherwise, the ruling path had a number of segments, so our result
        # must be an absolute path (unless we only want a subpath result, in
        # which case none exists).
        elif subPathOnly:
            return None
        else:
            relativePath = '/' + targetPath
    elif traverse > 0:
        if subPathOnly:
            return None
        relativePath = (("../" * traverse) +
                        '/'.join(targetPathSegments[i:]))
    # If the ith segment of the target path is empty and that is not the
    # final segment, then we need to precede the path with "./" to make it a
    # relative path.
    elif (len(targetPathSegments) > i + 1 and
          '' == targetPathSegments[i]):
        relativePath = "./" + '/'.join(targetPathSegments[i:])
    else:
        relativePath = '/'.join(targetPathSegments[i:])

    return unsplit_uri_ref([None, None, relativePath] + splitTarget[3:])


def remove_dot_segments(path):
    """
    Supports absolutize() by implementing the remove_dot_segments function
    described in RFC 3986 sec. 5.2.  It collapses most of the '.' and '..'
    segments out of a path without eliminating empty segments. It is intended
    to be used during the path merging process and may not give expected
    results when used independently. Use normalize_path_segments() or
    normalize_path_segments_in_uri() if more general normalization is desired.
    """
    # return empty string if entire path is just "." or ".."
    if path == '.' or path == '..':
        return path[0:0] # preserves string type
    # remove all "./" or "../" segments at the beginning
    while path:
        if path[:2] == './':
            path = path[2:]
        elif path[:3] == '../':
            path = path[3:]
        else:
            break
    # We need to keep track of whether there was a leading slash,
    # because we're going to drop it in order to prevent our list of
    # segments from having an ambiguous empty first item when we call
    # split().
    leading_slash = False
    if path[:1] == '/':
        path = path[1:]
        leading_slash = True
    # replace a trailing "/." with just "/"
    if path[-2:] == '/.':
        path = path[:-1]
    # convert the segments into a list and process each segment in
    # order from left to right.
    segments = path.split('/')
    keepers = []
    segments.reverse()
    while segments:
        seg = segments.pop()
        # '..' means drop the previous kept segment, if any.
        # If none, and if the path is relative, then keep the '..'.
        # If the '..' was the last segment, ensure
        # that the result ends with '/'.
        if seg == '..':
            if keepers:
                keepers.pop()
            elif not leading_slash:
                keepers.append(seg)
            if not segments:
                keepers.append('')
        # ignore '.' segments and keep all others, even empty ones
        elif seg != '.':
            keepers.append(seg)
    # reassemble the kept segments
    return leading_slash * '/' + '/'.join(keepers)


def normalize_case(iri_ref, doHost=False):
    """
    Returns the given URI reference with the case of the scheme,
    percent-encoded octets, and, optionally, the host, all normalized,
    implementing section 6.2.2.1 of RFC 3986. The normal form of
    scheme and host is lowercase, and the normal form of
    percent-encoded octets is uppercase.

    The URI reference can be given as either a string or as a sequence as
    would be provided by the split_uri_ref function. The return value will
    be a string or tuple.
    """
    if not isinstance(iri_ref, (tuple, list)):
        iri_ref = split_uri_ref(iri_ref)
        tup = None
    else:
        tup = True
    # normalize percent-encoded octets
    newRef = []
    for component in iri_ref:
        if component:
            newRef.append(re.sub('%([0-9a-f][0-9a-f])',
                          lambda m: m.group(0).upper(), component))
        else:
            newRef.append(component)
    # normalize scheme
    scheme = newRef[0]
    if scheme:
        scheme = scheme.lower()
    # normalize host
    authority = newRef[1]
    if doHost:
        if authority:
            userinfo, host, port = split_authority(authority)
            authority = ''
            if userinfo is not None:
                authority += '%s@' % userinfo
            authority += host.lower()
            if port is not None:
                authority += ':%s' % port

    res = (scheme, authority, newRef[2], newRef[3], newRef[4])
    if tup:
        return res
    else:
        return unsplit_uri_ref(res)


def normalize_percent_encoding(s):
    """
    Given a string representing a URI reference or a component thereof,
    returns the string with all percent-encoded octets that correspond to
    unreserved characters decoded, implementing section 6.2.2.2 of RFC
    3986.

    >>> u0 = 'http://host/abc%E2%80%A2/x/y/z'
    >>> u1 = normalize_percent_encoding(u0)
    >>> hex(ord(u1[15]))
    '0x2022'
    """
    return percent_decode(s, decodable=PERCENT_DECODE_BYTES)


def normalize_path_segments(path):
    """
    Given a string representing the path component of a URI reference having a
    hierarchical scheme, returns the string with dot segments ('.' and '..')
    removed, implementing section 6.2.2.3 of RFC 3986. If the path is
    relative, it is returned with no changes.
    """
    if not path or path[:1] != '/':
        return path
    else:
        return remove_dot_segments(path)


def normalize_path_segments_in_uri(uri):
    """
    Given a string representing a URI or URI reference having a hierarchical
    scheme, returns the string with dot segments ('.' and '..') removed from
    the path component, implementing section 6.2.2.3 of RFC 3986. If the
    path is relative, the URI or URI reference is returned with no changes.
    """
    components = list(split_uri_ref(uri))
    components[2] = normalize_path_segments(components[2])
    return unsplit_uri_ref(components)


#=============================================================================
# RFC 3151 implementation
#

def urn_to_public_id(urn):
    """
    Converts a URN that conforms to RFC 3151 to a public identifier.

    For example, the URN
    "urn:publicid:%2B:IDN+example.org:DTD+XML+Bookmarks+1.0:EN:XML"
    will be converted to the public identifier
    "+//IDN example.org//DTD XML Bookmarks 1.0//EN//XML"

    Raises a ValueError if the given URN cannot be converted.
    Query and fragment components, if present, are ignored.
    """
    if urn is not None and urn:
        (scheme, auth, path, query, frag) = split_uri_ref(urn)
        if scheme is not None and scheme.lower() == 'urn':
            pp = path.split(':', 1)
            if len(pp) > 1:
                urn_scheme = percent_decode(pp[0])
                if urn_scheme == 'publicid':
                    publicid = pp[1].replace('+', ' ')
                    publicid = publicid.replace(':', '//')
                    publicid = publicid.replace(';', '::')
                    publicid = percent_decode(publicid)
                    return publicid

    raise ValueError("A public ID cannot be derived from URN {urn} "
                "because it does not conform to RFC 3151.".format(urn=urn))


def public_id_to_urn(publicid):
    """
    Converts a public identifier to a URN that conforms to RFC 3151.
    """
    # 1. condense whitespace, XSLT-style
    publicid = re.sub('[ \t\r\n]+', ' ', publicid.strip())
    # 2. // -> :
    #    :: -> ;
    #    space -> +
    #    + ; ' ? # % / : -> percent-encode
    #    (actually, the intent of the RFC is to not conflict with RFC 2396,
    #     so any character not in the unreserved set must be percent-encoded)
    r = ':'.join([';'.join([percent_encode(dcpart, spaceToPlus=True)
                            for dcpart in dspart.split('::')])
                  for dspart in publicid.split('//')])
    return 'urn:publicid:%s' % r


#=============================================================================
# Miscellaneous public functions
#

SCHEME_PATTERN = re.compile(r'([a-zA-Z][a-zA-Z0-9+\-.]*):')
def get_scheme(iri_ref):
    """
    Obtains, with optimum efficiency, just the scheme from a URI reference.
    Returns a string, or if no scheme could be found, returns None.
    """
    # Using a regex seems to be the best option. Called 50,000 times on
    # different URIs, on a 1.0-GHz PIII with FreeBSD 4.7 and Python
    # 2.2.1, this method completed in 0.95s, and 0.05s if there was no
    # scheme to find. By comparison,
    #   urllib.splittype()[0] took 1.5s always;
    #   Ft.Lib.Uri.split_uri_ref()[0] took 2.5s always;
    #   urlparse.urlparse()[0] took 3.5s always.
    m = SCHEME_PATTERN.match(iri_ref)
    if m is None:
        return None
    else:
        return m.group(1)


def strip_fragment(iri_ref):
    """
    Returns the given URI or URI reference with the fragment component, if
    any, removed.
    """
    return split_fragment(iri_ref)[0]


def is_absolute(identifier):
    """
    Given a string believed to be a URI or URI reference, tests that it is
    absolute (as per RFC 3986), not relative -- i.e., that it has a scheme.
    """
    # We do it this way to avoid compiling another massive regex.
    return get_scheme(identifier) is not None


_ntPathToUriSetupCompleted = False
def _initNtPathPattern():
    """
    Called internally to compile the regular expression used by
    os_path_to_uri() on Windows just once, the first time the function is
    called.
    """
    global _ntPathToUriSetupCompleted
    if _ntPathToUriSetupCompleted:
        return
    # path variations we try to handle:
    #
    # a\b\c (a relative path)
    #    file:a/b/c is the best we can do.
    #    Dot segments should not be collapsed in the final URL.
    #
    # \a\b\c
    #    file:///a/b/c is correct
    #
    # C:\a\b\c
    #    urllib.urlopen() requires file:///C|/a/b/c or ///C|/a/b/c
    #     because it currently relies on urllib.url2pathname().
    #    Windows resolver will accept the first or file:///C:/a/b/c
    #
    # \\host\share\x\y\z
    #    Windows resolver accepts file://host/share/x/y/z
    #    Netscape (4.x?) accepts file:////host/share/x/y/z
    #
    # If an entire drive is shared, the share name might be
    #  $drive$, like this: \\host\$c$\a\b\c
    #  We could recognize it as a drive letter, but it's probably
    #  best not to treat it specially, since it will never occur
    #  without a host. It's just another share name.
    #
    # There's also a weird C:\\host\share\x\y\z convention
    #  that is hard to find any information on. Presumably the C:
    #  is ignored, but the question is do we put it in the URI?
    #
    # So the format, in ABNF, is roughly:
    # [ drive ":" ] ( [ "\\" host "\" share ] abs-path ) / rel-path
    drive         = r'(?P<drive>[A-Za-z])'
    host          = r'(?P<host>[^\\]*)'
    share         = r'(?P<share>[^\\]+)'
    abs_path      = r'(?P<abspath>\\(?:[^\\]+\\?)*)'
    rel_path      = r'(?P<relpath>(?:[^\\]+\\?)*)'
    NT_PATH_REGEX = r"^(?:%s:)?(?:(?:(?:\\\\%s\\%s)?%s)|%s)$" % (
                        drive,
                        host,
                        share,
                        abs_path,
                        rel_path)
    global NT_PATH_PATTERN
    NT_PATH_PATTERN = re.compile(NT_PATH_REGEX)
    # We can now use NT_PATH_PATTERN.match(path) to parse the path and use
    #  the returned object's .groupdict() method to get a dictionary of
    #  path subcomponents. For example,
    #  NT_PATH_PATTERN.match(r"\\h\$c$\x\y\z").groupdict()
    #  yields
    #  {'abspath': r'\x\y\z',
    #   'share': '$c$',
    #   'drive': None,
    #   'host': 'h',
    #   'relpath': None
    #  }
    # Note that invalid paths such as r'\\foo\bar'
    #  (a UNC path with no trailing '\') will not match at all.
    _ntPathToUriSetupCompleted = True
    return


def _splitNtPath(path):
    """
    Called internally to get a tuple representing components of the given
    Windows path.
    """
    if not _ntPathToUriSetupCompleted:
        _initNtPathPattern()
    m = NT_PATH_PATTERN.match(path)
    if not m:
        raise ValueError("Path {path} is not a valid Windows path.".format(path=path))
    components = m.groupdict()
    (drive, host, share, abspath, relpath) = (
        components['drive'],
        components['host'],
        components['share'],
        components['abspath'],
        components['relpath'],
        )
    return (drive, host, share, abspath, relpath)


def _get_drive_letter(s):
    """
    Called internally to get a drive letter from a string, if the string
    is a drivespec.
    """
    if len(s) == 2 and s[1] in ':|' and s[0] in ascii_letters:
        return s[0]
    return


def os_path_to_uri(path, attemptAbsolute=True, osname=None):
    r"""This function converts an OS-specific file system path to a URI of
    the form 'file:///path/to/the/file'.

    In addition, if the path is absolute, any dot segments ('.' or '..') will
    be collapsed, so that the resulting URI can be safely used as a base URI
    by functions such as absolutize().

    The given path will be interpreted as being one that is appropriate for
    use on the local operating system, unless a different osname argument is
    given.

    If the given path is relative, an attempt may be made to first convert
    the path to absolute form by interpreting the path as being relative
    to the current working directory.  This is the case if the attemptAbsolute
    flag is True (the default).  If attemptAbsolute is False, a relative
    path will result in a URI of the form file:relative/path/to/a/file .

    attemptAbsolute has no effect if the given path is not for the
    local operating system.

    On Windows, the drivespec will become the first step in the path component
    of the URI. If the given path contains a UNC hostname, this name will be
    used for the authority component of the URI.

    Warning: Some libraries, such as urllib.urlopen(), may not behave as
    expected when given a URI generated by this function. On Windows you may
    want to call re.sub('(/[A-Za-z]):', r'\1|', uri) on the URI to prepare it
    for use by functions such as urllib.url2pathname() or urllib.urlopen().

    This function is similar to urllib.pathname2url(), but is more featureful
    and produces better URIs.
    """
    # Problems with urllib.pathname2url() on all platforms include:
    # - the generated URL has no scheme component;
    # - percent-encoding is incorrect, due to urllib.quote() issues.
    #
    # Problems with urllib.pathname2url() on Windows include:
    # - trailing backslashes are ignored;
    # - all leading backslashes are considered part of the absolute
    #    path, so UNC paths aren't properly converted (assuming that
    #    a proper conversion would be to use the UNC hostname in the
    #    hostname component of the resulting URL);
    # - non-leading, consecutive backslashes are collapsed, which may
    #    be desirable but is correcting what is, arguably, user error;
    # - the presence of a letter followed by ":" is believed to
    #    indicate a drivespec, no matter where it occurs in the path,
    #    which may have been considered a safe assumption since the
    #    drivespec is the only place where ":" can legally, but there's
    #    no need to search the whole string for it;
    # - the ":" in a drivespec is converted to "|", a convention that
    #    is becoming increasingly less common. For compatibility, most
    #    web browser resolvers will accept either "|" or ":" in a URL,
    #    but urllib.urlopen(), relying on url2pathname(), expects "|"
    #    only. In our opinion, the callers of those functions should
    #    ensure that the arguments are what are expected. Our goal
    #    here is to produce a quality URL, not a URL designed to play
    #    nice with urllib's bugs & limitations.
    # - it treats "/" the same as "\", which results in being able to
    #    call the function with a posix-style path, a convenience
    #    which allows the caller to get sloppy about whether they are
    #    really passing a path that is apprropriate for the desired OS.
    #    We do this a lot in 4Suite.
    #
    # There is some disagreement over whether a drivespec should be placed in
    # the authority or in the path. Placing it in the authority means that
    # ":", which has a reserved purpose in the authority, cannot be used --
    # this, along with the fact that prior to RFC 3986, percent-encoded
    # octets were disallowed in the authority, is presumably a reason why "|"
    # is a popular substitute for ":". Using the authority also allows for
    # the drive letter to be retained whe resolving references like this:
    #   reference '/a/b/c' + base 'file://C|/x/y/z' = 'file://C|/a/b/c'
    # The question is, is that really the ideal result? Should the drive info
    # be inherited from the base URI, if it is unspecified in a reference
    # that is otherwise representing an absolute path? Using the authority
    # for this purpose means that it would be overloaded if we also used it
    # to represent the host part of a UNC path. The alternative is to put the
    # UNC host in the path (e.g. 'file:////host/share/path'), but when such a
    # URI is used as a base URI, relative reference resolution often returns
    # unexpected results.
    #
    osname = osname or os.name

    if osname == 'nt':
        if WINDOWS_SLASH_COMPAT:
            path = path.replace('/','\\')
        (drive, host, share, abspath, relpath) = _splitNtPath(path)
        if attemptAbsolute and relpath is not None and osname == os.name:
            path = os.path.join(os.getcwd(), relpath)
            (drive, host, share, abspath, relpath) = _splitNtPath(path)
        path = abspath or relpath
        path = '/'.join([percent_encode(seg) for seg in path.split('\\')])
        uri = 'file:'
        if host:
            uri += '//%s' % percent_encode(host)
        elif abspath:
            uri += '//'
        if drive:
            uri += '/%s:' % drive.upper()
        if share:
            uri += '/%s' % percent_encode(share)
        if abspath:
            path = remove_dot_segments(path)
        uri += path

    elif osname == 'posix':
        try:
            from posixpath import isabs
        except ImportError:
            isabs = lambda p: p[:1] == '/'
        pathisabs = isabs(path)
        if pathisabs:
            path = remove_dot_segments(path)
        elif attemptAbsolute and osname == os.name:
            path = os.path.join(os.getcwd(), path)
            pathisabs = isabs(path)
        path = '/'.join([percent_encode(seg) for seg in path.split('/')])
        if pathisabs:
            uri = 'file://%s' % path
        else:
            uri = 'file:%s' % path

    else:
        # 4Suite only supports posix and nt, so we're not going to worry about
        # improving upon urllib.pathname2url() for other OSes.
        if osname == os.name:
            from urllib import pathname2url
            if attemptAbsolute and not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
        else:
            try:
                module = '%surl2path' % osname
                exec('from %s import pathname2url' % module, globals(), locals())
            except ImportError:
                raise RuntimeError("Platform {platform} not supported by URI function "
                "{function}".format(platform=osname, function="os_path_to_uri"))
        uri = 'file:' + pathname2url(path)

    return uri


def uri_to_os_path(uri, attemptAbsolute=True, encoding='utf-8', osname=None):
    r"""
    This function converts a URI reference to an OS-specific file system path.

    If the URI reference is given as a Unicode string, then the encoding
    argument determines how percent-encoded components are interpreted, and
    the result will be a Unicode string. If the URI reference is a regular
    byte string, the encoding argument is ignored and the result will be a
    byte string in which percent-encoded octets have been converted to the
    bytes they represent. For example, the trailing path segment of
    'file:///a/b/%E2%80%A2' will by default be converted to '\u2022',
    because sequence E2 80 A2 represents character U+2022 in UTF-8. If the
    string were not Unicode, the trailing segment would become the 3-byte
    string '\xe2\x80\xa2'.

    The osname argument determines for what operating system the resulting
    path is appropriate. It defaults to os.name and is typically the value
    'posix' on Unix systems (including Mac OS X and Cygwin), and 'nt' on
    Windows NT/2000/XP.

    This function is similar to urllib.url2pathname(), but is more featureful
    and produces better paths.

    If the given URI reference is not relative, its scheme component must be
    'file', and an exception will be raised if it isn't.

    In accordance with RFC 3986, RFC 1738 and RFC 1630, an authority
    component that is the string 'localhost' will be treated the same as an
    empty authority.

    Dot segments ('.' or '..') in the path component are NOT collapsed.

    If the path component of the URI reference is relative and the
    attemptAbsolute flag is True (the default), then the resulting path
    will be made absolute by considering the path to be relative to the
    current working directory. There is no guarantee that such a result
    will be an accurate interpretation of the URI reference.

    attemptAbsolute has no effect if the
    result is not being produced for the local operating system.

    Fragment and query components of the URI reference are ignored.

    If osname is 'posix', the authority component must be empty or just
    'localhost'. An exception will be raised otherwise, because there is no
    standard way of interpreting other authorities. Also, if '%2F' is in a
    path segment, it will be converted to r'\/' (a backslash-escaped forward
    slash). The caller may need to take additional steps to prevent this from
    being interpreted as if it were a path segment separator.

    If osname is 'nt', a drivespec is recognized as the first occurrence of a
    single letter (A-Z, case-insensitive) followed by '|' or ':', occurring as
    either the first segment of the path component, or (incorrectly) as the
    entire authority component. A UNC hostname is recognized as a non-empty,
    non-'localhost' authority component that has not been recognized as a
    drivespec, or as the second path segment if the first path segment is
    empty. If a UNC hostname is detected, the result will begin with
    '\\<hostname>\'. If a drivespec was detected also, the first path segment
    will be '$<driveletter>$'. If a drivespec was detected but a UNC hostname
    was not, then the result will begin with '<driveletter>:'.

    Windows examples:
    'file:x/y/z' => r'x\y\z';
    'file:/x/y/z' (not recommended) => r'\x\y\z';
    'file:///x/y/z' => r'\x\y\z';
    'file:///c:/x/y/z' => r'C:\x\y\z';
    'file:///c|/x/y/z' => r'C:\x\y\z';
    'file:///c:/x:/y/z' => r'C:\x:\y\z' (bad path, valid interpretation);
    'file://c:/x/y/z' (not recommended) => r'C:\x\y\z';
    'file://host/share/x/y/z' => r'\\host\share\x\y\z';
    'file:////host/share/x/y/z' => r'\\host\share\x\y\z'
    'file://host/x:/y/z' => r'\\host\x:\y\z' (bad path, valid interp.);
    'file://localhost/x/y/z' => r'\x\y\z';
    'file://localhost/c:/x/y/z' => r'C:\x\y\z';
    'file:///C:%5Cx%5Cy%5Cz' (not recommended) => r'C:\x\y\z'
    """
    (scheme, authority, path) = split_uri_ref(uri)[0:3]
    if scheme and scheme != 'file':
        raise ValueError("Only a 'file' URI can be converted to an OS-specific path; "
                "URI given was {uri}".format(uri=uri))
    # enforce 'localhost' URI equivalence mandated by RFCs 1630, 1738, 3986
    if authority == 'localhost':
        authority = None
    osname = osname or os.name

    if osname == 'nt':
        # Get the drive letter and UNC hostname, if any. Fragile!
        unchost = None
        driveletter = None
        if authority:
            authority = percent_decode(authority, encoding=encoding)
            if _get_drive_letter(authority):
                driveletter = authority[0]
            else:
                unchost = authority
        if not (driveletter or unchost):
            # Note that we have to treat %5C (backslash) as a path separator
            # in order to catch cases like file:///C:%5Cx%5Cy%5Cz => C:\x\y\z
            # We will also treat %2F (slash) as a path separator for
            # compatibility.
            if WINDOWS_SLASH_COMPAT:
                regex = '%2[fF]|%5[cC]'
            else:
                regex = '%5[cC]'
            path = re.sub(regex, '/', path)
            segs = path.split('/')
            if not segs[0]:
                # //host/... => [ '', '', 'host', '...' ]
                if len(segs) > 2 and not segs[1]:
                    unchost = percent_decode(segs[2], encoding=encoding)
                    path = len(segs) > 3 and '/' + '/'.join(segs[3:]) or ''
                # /C:/...    => [ '', 'C:', '...' ]
                elif len(segs) > 1:
                    driveletter = _get_drive_letter(percent_decode(segs[1],
                                                   encoding=encoding))
                    if driveletter:
                        path = len(segs) > 2 and '/' + '/'.join(segs[2:]) or ''
            else:
                # C:/...     => [ 'C:', '...' ]
                driveletter = _get_drive_letter(percent_decode(segs[0],
                                                encoding=encoding))
                if driveletter:
                    path = len(segs) > 1 and path[2:] or ''



        # Do the conversion of the path part
        sep = '\\' # we could try to import from ntpath,
                   # but at this point it would just waste cycles.
        path = percent_decode(path.replace('/', sep), encoding=encoding)

        # Assemble and return the path
        if unchost:
            # It's a UNC path of the form \\host\share\path.
            # driveletter is ignored.
            path = r'%s%s%s' % (sep * 2, unchost, path)
        elif driveletter:
            # It's an ordinary Windows path of the form C:\x\y\z
            path = r'%s:%s' % (driveletter.upper(), path)
        # It's an ordinary Windows path of the form \x\y\z or x\y\z.
        # We need to make sure it doesn't end up looking like a UNC
        # path, so we discard extra leading backslashes
        elif path[:1] == '\\':
            path = re.sub(r'^\\+', '\\\\', path)
        # It's a relative path. If the caller wants it absolute, attempt to comply
        elif attemptAbsolute and osname == os.name:
            path = os.path.join(os.getcwd(), path)

        return path

    elif osname == 'posix':
        # a non-empty, non-'localhost' authority component is ambiguous on Unix
        if authority:
            raise ValueError("A URI containing a remote host name cannot be converted to a "
                " path on posix; URI given was {uri}".format(uri=uri))
        # %2F in a path segment would indicate a literal '/' in a
        # filename, which is possible on posix, but there is no
        # way to consistently represent it. We'll backslash-escape
        # the literal slash and leave it to the caller to ensure it
        # gets handled the way they want.
        path = percent_decode(re.sub('%2[fF]', '\\/', path), encoding=encoding)
        # If it's relative and the caller wants it absolute, attempt to comply
        if attemptAbsolute and osname == os.name and not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)

        return path

    else:
        # 4Suite only supports posix and nt, so we're not going to worry about
        # improving upon urllib.pathname2url() for other OSes.
        if osname == os.name:
            from urllib import url2pathname
        else:
            try:
                module = '%surl2path' % osname
                exec('from %s import url2pathname' % module, globals(), locals())
            except ImportError:
                raise RuntimeError("Platform {platform} not supported by URI function "
                "{function}".format(platform=osname, function="uri_to_os_path"))
        # drop the scheme before passing to url2pathname
        if scheme:
            uri = uri[len(scheme)+1:]
        return url2pathname(uri)

REG_NAME_HOST_PATTERN = re.compile(r"^(?:(?:[0-9A-Za-z\-_\.!~*'();&=+$,]|(?:%[0-9A-Fa-f]{2}))*)$")


def path_resolve(paths):
    """
    This function takes a list of file URIs.  The first can be
    absolute or relative to the URI equivalent of the current working
    directory. The rest must be relative to the first.
    The function converts them all to OS paths appropriate for the local
    system, and then creates a single final path by resolving each path
    in the list against the following one. This final path is returned
    as a URI.
    """
    if not paths: return paths
    paths = [uri_to_os_path(p, attemptAbsolute=False) for p in paths]
    if not os.path.isabs(paths[0]):
        paths[0] = os.path.join(os.getcwd(), paths[0])
    resolved = reduce(lambda a, b: \
                       basejoin(os.path.isdir(a)
                                 and os_path_to_uri(
                                      os.path.join(a, ''),
                                      attemptAbsolute=False,
                                     ) or os_path_to_uri(a, attemptAbsolute=False),
                                os_path_to_uri(b, attemptAbsolute=False)[5:]),
                       paths)
    return resolved


def basejoin(base, iri_ref):
    """
    Merges a base URI reference with another URI reference, returning a
    new URI reference.

    It behaves exactly the same as absolutize(), except the arguments
    are reversed, and it accepts any URI reference (even a relative URI)
    as the base URI. If the base has no scheme component, it is
    evaluated as if it did, and then the scheme component of the result
    is removed from the result, unless the iri_ref had a scheme. Thus, if
    neither argument has a scheme component, the result won't have one.

    This function is named basejoin because it is very much like
    urllib.basejoin(), but it follows the current RFC 3986 algorithms
    for path merging, dot segment elimination, and inheritance of query
    and fragment components.

    WARNING: This function exists for 2 reasons: (1) because of a need
    within the 4Suite repository to perform URI reference absolutization
    using base URIs that are stored (inappropriately) as absolute paths
    in the subjects of statements in the RDF model, and (2) because of
    a similar need to interpret relative repo paths in a 4Suite product
    setup.xml file as being relative to a path that can be set outside
    the document. When these needs go away, this function probably will,
    too, so it is not advisable to use it.
    """
    if is_absolute(base):
        return absolutize(iri_ref, base)
    else:
        dummyscheme = 'basejoin'
        res = absolutize(iri_ref, '%s:%s' % (dummyscheme, base))
        if is_absolute(iri_ref):
            # scheme will be inherited from iri_ref
            return res
        else:
            # no scheme in, no scheme out
            return res[len(dummyscheme)+1:]


def join(*uriparts):
    """
    Merges a series of URI reference parts, returning a new URI reference.

    Much like iri.basejoin, but takes multiple arguments
    """
    if len(uriparts) == 0:
        raise TypeError("FIXME...")
    elif len(uriparts) == 1:
        return uriparts[0]
    else:
        base = uriparts[0]
        for part in uriparts[1:]:
            base = basejoin(base.rstrip(DEFAULT_HIERARCHICAL_SEP) + DEFAULT_HIERARCHICAL_SEP, part)
        return base


#generate_iri
#Use:
#from uuid import *; newuri = uuid4().urn

#=======================================================================
#
# Further reading re: percent-encoding
#
# http://lists.w3.org/Archives/Public/ietf-http-wg/2004JulSep/0009.html
#
#=======================================================================
#
# 'file:' URI notes
#
# 'file:' URI resolution is difficult to get right, because the 'file'
# URL scheme is underspecified, and is handled by resolvers in very
# lenient and inconsistent ways.
#
# RFC 3986 provides definitive clarification on how all URIs,
# including the quirky 'file:' ones, are to be interpreted for purposes
# of resolution to absolute form, so that is what we implement to the
# best of our ability.
#
#-----------------------------------------------------------------------
#
# Notes from our previous research on 'file:' URI resolution:
#
# According to RFC 2396 (original), these are valid absolute URIs:
#  file:/autoexec.bat     (scheme ":" abs_path)
#  file:///autoexec.bat   (scheme ":" net_path)
#
# This one is valid but is not what you'd expect it to be:
#
#  file://autoexec.bat    (authority = autoexec.bat, no abs_path)
#
# If you have any more than 3 slashes, it's OK because each path segment
# can be an empty string.
#
# This one is valid too, although everything after 'file:' is
# considered an opaque_part (note that RFC 3986 changes this):
#
#   file:etc/passwd
#
# Unescaped backslashes are NOT allowed in URIs, ever.
# It is not possible to use them as path segment separators.
# Yet... Windows Explorer will accept these:
#   file:C:\WINNT\setuplog.txt
#   file:/C:\WINNT\setuplog.txt
#   file:///C:\WINNT\setuplog.txt
# However, it will also accept "|" in place of the colon after the drive:
#   file:C|/WINNT/setuplog.txt
#   file:/C|/WINNT/setuplog.txt
#   file:///C|/WINNT/setuplog.txt
#
# RFC 1738 says file://localhost/ and file:/// are equivalent;
# localhost in this case is always the local machine, no matter what
# your DNS says.
#
# Basically, any file: URI is valid. Good luck resolving them, though.
#
# Jeremy's idea is to not use open() or urllib.urlopen() on Windows;
# instead, use a C function that wraps Windows' generic open function,
# which resolves any path or URI exactly as Explorer would (he thinks).
#
#-----------------------------------------------------------------------
#
# References for further research on 'file:' URI resolution:
#  http://mail.python.org/pipermail/xml-sig/2001-February/004572.html
#  http://mail.python.org/pipermail/xml-sig/2001-March/004791.html
#  http://mail.python.org/pipermail/xml-sig/2002-August/008236.html
#  http://www.perldoc.com/perl5.8.0/lib/URI/file.html
#  http://lists.w3.org/Archives/Public/uri/2004Jul/0013.html
#
#=======================================================================
