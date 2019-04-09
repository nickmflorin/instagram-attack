from __future__ import absolute_import

from collections import Iterable


__all__ = ('ensure_iterable', 'array', 'array_string')


def ensure_iterable(arg):
    if isinstance(arg, str):
        return [arg]
    elif not isinstance(arg, Iterable):
        return [arg]
    return arg


def array(*values):
    return [val for val in values if val is not None]


def array_string(*values, separator=" "):
    values = array(*values)
    return separator.join(values)
