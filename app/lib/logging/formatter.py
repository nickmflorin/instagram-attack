from __future__ import absolute_import

import logging

from app.lib.utils import RecordFormatter, RESET_SEQ, RecordAttributes


class LogLineItem(object):
    def __init__(self, *items, separator=' '):
        from app.lib.utils import ensure_iterable

        self.items = ensure_iterable(items)
        self.separator = separator

    @property
    def filled_items(self):
        return [item for item in self.items if item]

    @property
    def empty(self):
        return len(self.filled_items) == 0

    def to_string(self):
        items = [item for item in self.items if item]

        separator = self.separator
        if self.separator != ' ':
            separator = ' %s ' % self.separator
        string_format = separator.join(["%s" % item for item in items])
        return string_format


class LogLine(object):

    def __init__(self, *items, indent=0, newline=False, header=None):
        from app.lib.utils import ensure_iterable

        self.indent = indent
        self.newline = newline
        self.header = header

        items = ensure_iterable(items)

        self.items = []
        items = ensure_iterable(items)
        for item in items:
            if not isinstance(item, LogLineItem):
                self.items.append(LogLineItem(item))
            else:
                self.items.append(item)

    @property
    def filled_items(self):
        return [item for item in self.items if not item.empty]

    @property
    def empty(self):
        return len(self.filled_items) == 0

    def to_string(self):
        if not self.empty:
            line_item_string = " ".join([item.to_string() for item in self.filled_items])
            if self.header:
                line_item_string = "%s: %s" % (
                    RecordAttributes.HEADER.format(self.header), line_item_string)
            if self.indent:
                line_item_string = "%s%s" % ((self.indent * " "), line_item_string)
            if self.newline:
                line_item_string = "%s%s" % ("\n", line_item_string)
            return line_item_string


class LogLines(object):
    def __init__(self, *items, newlines=False, newline=False, indent=None):
        from app.lib.utils import ensure_iterable

        self.items = ensure_iterable(items)
        self.newlines = newlines
        self.newline = newline
        self.indent = indent

        if self.newlines:
            for item in self.items:
                item.newline = True

        if self.indent:
            for item in self.items:
                item.indent = self.indent

    @property
    def filled_items(self):
        return [item for item in self.items if not item.empty]

    @property
    def empty(self):
        return len(self.filled_items) == 0

    def to_string(self):
        log_lines_string = ""
        for i, line in enumerate(self.filled_items):
            log_lines_string += line.to_string()
        if self.newline:
            return "%s\n" % log_lines_string
        return log_lines_string


class AppLogFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def format(self, record):
        wrapper = RecordFormatter(record)

        formatted_date = logging.Formatter.format(self, record)
        raw_date_string = formatted_date.split('[33m')[1].split(RESET_SEQ)[0]
        indentation = len(f"[{raw_date_string}] ")

        return LogLines(
            LogLine(
                LogLineItem(formatted_date),  # Time Prefix
                LogLineItem(
                    wrapper._levelname,
                    wrapper._name,
                    wrapper._threadName,
                    wrapper._task,
                    separator='-',
                )
            ),
            LogLine(
                wrapper._msg,
                newline=True,
                indent=indentation
            ),
            LogLines(
                LogLine(
                    wrapper._status_code,
                    header="Status Code"
                ),
                LogLine(
                    wrapper._proxy,
                    header="Proxy"
                ),
                LogLine(
                    wrapper._token,
                    header="Token"
                ),
                LogLine(
                    wrapper._password,
                    header="Password"
                ),
                LogLine(
                    wrapper._traceback
                ),
                indent=indentation,
                newlines=True,
            ),
            newline=True
        ).to_string()
