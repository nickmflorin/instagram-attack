from __future__ import absolute_import

import contextlib
import logbook
import progressbar
import sys

from .formatter import app_formatter


__all__ = ('AppLogger', 'log_handling', )


def _stream_handler(config=None, format_string=None, filter=None):
    handler = logbook.StreamHandler(
        sys.stdout,
        level=config.level if config else 'INFO',
        filter=filter,
        bubble=True
    )
    handler.format_string = format_string
    return handler


def base_handler(config=None):
    """
    We want to lazy evaluate the initialization of StreamHandler for purposes
    of progressbar implementation with logging.
    """
    handler = _stream_handler(config=config)
    handler.formatter = app_formatter
    return handler


@contextlib.contextmanager
def log_handling(config=None):

    progressbar.streams.wrap_stderr()
    progressbar.streams.wrap_stdout()

    base = base_handler(config=config)
    with base:
        yield


class AppLogger(logbook.Logger):
    pass
