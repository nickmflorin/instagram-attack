from __future__ import absolute_import

from argparse import ArgumentTypeError


def validate_log_level(val):
    levels = [
        'INFO',
        'DEBUG',
        'WARNING',
        'SUCCESS',
        'CRITICAL',
    ]

    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in levels:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


def validate_method(value):
    methods = {
        'get': 'GET',
        'post': 'POST'
    }
    method = methods.get(value.lower())
    if not method:
        raise ArgumentTypeError('Invalid method.')
    return method
