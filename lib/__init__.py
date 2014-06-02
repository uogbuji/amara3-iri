#amara3.lib

import gettext
gettext.install('amara3')

from .version import version_info
__version__ = '.'.join(version_info)

class IriError(Exception):
    """
    Exception related to URI/IRI processing
    """
    pass
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
            IriError.IDNA_UNSUPPORTED: _(
                "The URI ref %(uri)r cannot be made urllib-safe on this "
                "version of Python (IDNA encoding unsupported)."),
            IriError.DENIED_BY_RULE: _(
                "Access to IRI %(uri)r was denied by action of an IRI restriction"),
            }
'''
