"""
[x] NOTE:
--------
Because the ext module is used both at the upper levels by setuptools, the config
and at lower levels in core, it is important that all imports into the files
in these modules be lazy imported.

The functionality in these modules should not depend on functionality elsehwhere
in the app, except for top level constants.
"""

import sys


PY2 = sys.version_info[0] == 2
ENCODING = "utf-8"


if PY2:
    builtin_str = str
    bytes = str
    str = unicode  # noqa
    basestring = basestring  # noqa

    def iteritems(dct):
        return dct.iteritems()


else:
    builtin_str = str
    bytes = bytes
    str = str
    basestring = (str, bytes)

    def iteritems(dct):
        return dct.items()


def to_unicode(text_type, encoding=ENCODING):
    if isinstance(text_type, bytes):
        return text_type.decode(encoding)
    return text_type


def safe_text(text):
    if PY2:
        return to_unicode(text)
    return text
