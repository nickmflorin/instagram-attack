import logging

import contextlib
import progressbar
from plumbum import colors
import traceback
import sys

from .utils import record_context
from .formats import (
    LoggingLevels, LOG_FORMAT_STRING, SIMPLE_FORMAT_STRING, BARE_FORMAT_STRING)


__all__ = ('AppLogger', 'log_environment', )


class TypeFilter(logging.Filter):

    def __init__(self, require=None, disallow=None, *args, **kwargs):
        super(TypeFilter, self).__init__(*args, **kwargs)
        self.require = require
        self.disallow = disallow

    def filter(self, record):
        if self.require:
            if not all([x in record.__dict__ for x in self.require]):
                return False

        if self.disallow:
            if any([x in record.__dict__ for x in self.disallow]):
                return False

        return True


class CustomFormatter(logging.Formatter):

    def __init__(self, format_string=LOG_FORMAT_STRING, **kwargs):
        super(CustomFormatter, self).__init__(**kwargs)
        self.format_string = format_string

    def format(self, record):
        context = record_context(record)
        format_string = self.format_string(record)
        return format_string.format(context)


class CustomerHandler(logging.StreamHandler):

    def __init__(self, filter=None, format_string=LOG_FORMAT_STRING):
        super(CustomerHandler, self).__init__()

        formatter = CustomFormatter(format_string=format_string)
        self.setFormatter(formatter)

        if filter:
            self.addFilter(filter)


class AppLogger(logging.Logger):

    HANDLERS = [
        CustomerHandler(
            format_string=BARE_FORMAT_STRING,
            filter=TypeFilter(require=['bare']),
        ),
        CustomerHandler(
            format_string=SIMPLE_FORMAT_STRING,
            filter=TypeFilter(require=['simple']),
        ),
        CustomerHandler(
            format_string=LOG_FORMAT_STRING,
            filter=TypeFilter(disallow=['bare', 'simple'])
        )
    ]

    def __init__(self, *args, **kwargs):
        super(AppLogger, self).__init__(*args, **kwargs)
        self.line_index = 0
        self.add_handlers()

    def add_handlers(self):
        for handler in self.HANDLERS:
            self.addHandler(handler)

    def default(self, record, attr, default=None):
        setattr(record, attr, getattr(record, attr, default))

    def makeRecord(self, *args, **kwargs):
        record = super(AppLogger, self).makeRecord(*args, **kwargs)
        setattr(record, 'level', LoggingLevels[record.levelname])

        self.default(record, 'line_index', default=None)
        self.default(record, 'highlight', default=False)
        self.default(record, 'color', default=None)

        self.default(record, 'is_exception', default=False)
        if isinstance(record.msg, Exception):
            record.is_exception = True

        if record.color:
            if isinstance(record.color, str):
                setattr(record, 'color', colors.fg(record.color))

        return record

    def simple(self, message, color=None, extra=None):
        default = {'color': color, 'simple': True}
        extra = extra or {}
        default.update(**extra)
        self.info(message, extra=default)

    def bare(self, message, color='darkgray', extra=None):
        default = {'color': color, 'bare': True}
        extra = extra or {}
        default.update(**extra)
        self.info(message, extra=default)

    def before_lines(self):
        self.line_index = 0

    def line(self, item, color='darkgray', numbered=True):
        extra = {}
        if numbered:
            extra = {'line_index': self.line_index + 1}
            self.line_index += 1
        self.bare(item, color=color, extra=extra)

    def line_by_line(self, lines, color='darkgray', numbered=True):
        self.before_lines()
        for line in lines:
            self.line(line, color=color, numbered=numbered)

    # We might now need this anymore?
    def traceback(self, ex, ex_traceback=None, raw=False):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        if ex_traceback is None:
            ex_traceback = ex.__traceback__

        tb_lines = [
            line.rstrip('\n') for line in
            traceback.format_exception(ex.__class__, ex, ex_traceback)
        ]

        # This can be used if we want to just output the raw error.
        if raw:
            for line in tb_lines:
                sys.stderr.write("%s\n" % line)
        else:
            self.error("\n".join(tb_lines), extra={'no_indent': True})


@contextlib.contextmanager
def log_environment():

    def _init_progressbar():
        progressbar.streams.wrap_stderr()
        progressbar.streams.wrap_stdout()

    def _deinit_progressbar():
        progressbar.streams.unwrap_stdout()
        progressbar.streams.unwrap_stderr()

    try:
        _init_progressbar()
        yield
    finally:
        _deinit_progressbar()
