from __future__ import absolute_import

import contextlib
import logbook
import progressbar
import sys
import traceback

from .formatter import app_formatter


__all__ = ('AppLogger', 'log_handling', 'handle_global_exception', )


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


def handle_global_exception(exc, callback=None):
    """
    Can only handle instances of traceback.TracebackException
    """
    tb = exc.exc_traceback

    log = tb.tb_frame.f_globals.get('log')
    if not log:
        log = tb.tb_frame.f_locals.get('log')

    # Array of lines for the stack trace - might be useful later.
    # trace = traceback.format_exception(ex_type, ex, tb, limit=3)
    log.exception(exc, extra={
        'lineno': exc.stack[-1].lineno,
        'filename': exc.stack[-1].filename,
    })


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


class AppLogger(logbook.Logger):
    """
    TODO: For the traceback in start_and_done, we have to set it back one step
    so it shows the original location.
    """
    @contextlib.contextmanager
    def start_and_done(self, action_string, level='NOTICE', exit_level='DEBUG'):
        methods = {
            'INFO': self.info,
            'NOTICE': self.notice,
            'DEBUG': self.debug,
            'WARNING': self.warning,
        }
        method = methods[level.upper()]
        exit_method = methods[exit_level.upper()]

        # This doesn't seem to be working...
        stacks = traceback.extract_stack()
        stacks = [
            st for st in stacks if (all([
                not st.filename.startswith('/Library/Frameworks/'),
                not any([x in st.filename for x in ['stdin', 'stderr', 'stdout']]),
                __file__ not in st.filename,
            ]))
        ]

        try:
            method(f'{action_string}...', extra={
                'lineno': stacks[-1].lineno,
                'filename': stacks[-1].filename,
            })
            yield
        finally:
            exit_method(f'Done {action_string}.', extra={
                'lineno': stacks[-1].lineno,
                'filename': stacks[-1].filename,
            })
