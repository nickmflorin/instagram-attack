from __future__ import absolute_import

from argparse import ArgumentTypeError


def validate_proxy_sleep(n):
    try:
        return int(n)
    except TypeError:
        raise ArgumentTypeError("--proxysleep must be a valid integer")


def validate_limit(n):
    try:
        return int(n)
    except TypeError:
        raise ArgumentTypeError("--limit must be a valid integer")


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
