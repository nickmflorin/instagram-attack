import contextlib
import logbook
import progressbar
import sys

from .formatter import app_formatter


__all__ = ('log_handling', )


def _stream_handler(level='INFO', format_string=None, filter=None):
    handler = logbook.StreamHandler(
        sys.stdout,
        level=level,
        filter=filter,
        bubble=True
    )
    handler.format_string = format_string
    return handler


def base_handler(level=None):
    """
    We want to lazy evaluate the initialization of StreamHandler for purposes
    of progressbar implementation with logging.
    """
    handler = _stream_handler(level=level)
    handler.formatter = app_formatter
    return handler


class log_handling(object):

    def __init__(self, level):
        self.level = level

    def __call__(self, f):

        def wrapped(instance, *args, **kwargs):
            if self.level == 'self':
                self.level = getattr(instance, 'level')

            with self.context():
                return f(instance, *args, **kwargs)
        return wrapped

    @contextlib.contextmanager
    def context(self):
        self._init_progressbar()
        try:
            with base_handler(level=self.level):
                yield
        finally:
            self._deinit_progressbar()

    def _init_progressbar(self):
        progressbar.streams.wrap_stderr()
        progressbar.streams.wrap_stdout()

    def _deinit_progressbar(self):
        progressbar.streams.unwrap_stdout()
        progressbar.streams.unwrap_stderr()
