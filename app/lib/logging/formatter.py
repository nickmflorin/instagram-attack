from __future__ import absolute_import

import logging

from app.lib.utils import ensure_iterable

from .utils import RecordWrapper
from .constants import RESET_SEQ


class LogLineItem(object):
    def __init__(self, *items, separator=' '):
        self.items = ensure_iterable(items)
        self.separator = separator

    def to_string(self):
        items = [item for item in self.items if item]

        separator = self.separator
        if self.separator != ' ':
            separator = ' %s ' % self.separator
        string_format = separator.join(["%s" % item for item in items])
        return string_format


class LogLine(object):

    def __init__(self, *items, indent=0, newline=False):
        self.items = ensure_iterable(items)
        self.indent = indent
        self.newline = newline

    def to_string(self):
        line_item_string = " ".join([item.to_string() for item in self.items])
        if self.indent:
            line_item_string = "%s%s" % ((self.indent * " "), line_item_string)
        if self.newline:
            line_item_string = "%s%s" % ("\n", line_item_string)
        return line_item_string


class LogLines(object):
    def __init__(self, *items):
        self.items = ensure_iterable(items)

    def to_string(self):
        log_lines_string = ""
        for i, line in enumerate(self.items):
            log_lines_string += line.to_string()
        return log_lines_string


class AppLogFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def format(self, record):
        wrapper = RecordWrapper(record)

        formatted_date = logging.Formatter.format(self, record)
        raw_date_string = formatted_date.split('[33m')[1].split(RESET_SEQ)[0]
        indentation = len(f"[{raw_date_string}] ")

        return LogLines(
            LogLine(
                LogLineItem(formatted_date),  # Time Prefix
                LogLineItem(
                    wrapper._levelname(formatted=True),
                    wrapper._threadName(formatted=True),
                    wrapper._task(formatted=True),
                    separator='-',
                )
            ),
            LogLine(
                LogLineItem(
                    wrapper._status_code(formatted=True),
                    wrapper._msg(formatted=True),
                    wrapper._url(formatted=True),
                    wrapper._proxy(formatted=True),
                    wrapper._token(formatted=True),
                    wrapper._traceback(formatted=True)
                ),
                indent=indentation,
                newline=True,
            )
        ).to_string()
