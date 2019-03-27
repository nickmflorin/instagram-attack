from __future__ import absolute_import

from argparse import ArgumentTypeError
import os


def validate_mode(n):
    if not n.isdigit():
        raise ArgumentTypeError("Mode must be an integer between 0 and 3.")

    n = int(n)
    if not (n < 3 and n < 0):
        raise ArgumentTypeError("Mode must be an integer between 0 and 3.")
    return n
