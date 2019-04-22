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


def filter_context(context_id):
    def _filter_context(r, h):
        return (r.extra['context'] and
            r.extra['context'].context_id == context_id)
    return _filter_context


def base_handler(config=None):
    """
    We want to lazy evaluate the initialization of StreamHandler for purposes
    of progressbar implementation with logging.
    """
    handler = _stream_handler(
        config=config,
    )
    handler.formatter = app_formatter
    return handler


def token_handler(config=None):
    handler = _stream_handler(
        config=config,
        filter=filter_context('token'),
    )
    handler.formatter = app_formatter
    return handler


def login_handler(config=None):
    handler = _stream_handler(
        config=config,
        filter=filter_context('login'),
    )
    handler.formatter = app_formatter
    return handler


def attempt_handler(config=None):
    handler = _stream_handler(
        config=config,
        filter=filter_context('attempt'),
    )
    handler.formatter = app_formatter
    return handler


@contextlib.contextmanager
def log_handling(config=None):

    progressbar.streams.wrap_stderr()
    progressbar.streams.wrap_stdout()

    base = base_handler(config=config)
    token = token_handler(config=config)
    login = login_handler(config=config)
    attempt = attempt_handler(config=config)

    with base, token, login, attempt:
        yield


class AppLogger(logbook.Logger):
    pass
