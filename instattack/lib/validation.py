from __future__ import absolute_import

from argparse import ArgumentTypeError

from instattack.settings import LEVELS, METHODS


__all__ = ('validate_log_level', 'validate_method', )


def validate_log_level(val):
    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in LEVELS:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


def validate_method(value):
    if value.upper() not in METHODS:
        raise ArgumentTypeError('Invalid method.')
    return value.upper()
