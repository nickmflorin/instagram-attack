from __future__ import absolute_import

import logging

from colorama import init

from .constants import Format, Colors, Styles
from .formatter import AppLogFormatter


__all__ = ('AppLogger', )


class AppLogger(logging.Logger):

    DATE_FORMAT_OBJ = Format(color=Colors.YELLOW, styles=Styles.DIM)
    DATE_FORMAT = DATE_FORMAT_OBJ('%Y-%m-%d %H:%M:%S')

    FORMAT = "[%(asctime)s]"

    __formatter__ = AppLogFormatter

    def __init__(self, name):
        init(autoreset=True)
        logging.Logger.__init__(self, name)

        logging.SUCCESS = 25  # between WARNING and INFO
        logging.addLevelName(logging.SUCCESS, 'SUCCESS')

        self.formatter = self.__formatter__(self.FORMAT, datefmt=self.DATE_FORMAT)

        handler = logging.StreamHandler()
        handler.setFormatter(self.formatter)

        self.addHandler(handler)

    def makeRecord(self, name, lvl, fn, lno, msg, args, exc_info, func, extra, sinfo):
        record = super(AppLogger, self).makeRecord(name, lvl, fn, lno, msg, args,
            exc_info, func, extra, sinfo)
        """
        Currently, we are using error handlers in order to raise certain exceptions
        so that they are not suppressed and hidden by asyncio.

        A side-effect is that the line number and file name of those raised
        exceptions are not from the original stack trace, but the stack trace
        of where they are handled by the handlers (usually in utils).

        We are not allowed to override these values directly on the record instance,
        so we cannot use extra={'lineno': ..., 'filename': ...}, so instead
        we will use different parameters and have our handler override the
        formatted message.

        >>> log.warning("...", extra={'file_name': ..., 'line_no': ...})

        If file_name or line_no are present, they will override values for
        lineno and/or filename.
        """
        extra = extra or {}
        for key, val in extra.items():
            setattr(record, key, val)
        return record

    def stringify_item(self, key, val):
        bold_value = Styles.BOLD.encode(val)
        return f"{key}: {bold_value}"

    def stringify_items(self, **items):
        string_items = [self.stringify_item(key, val)
            for key, val in items.items()]
        return ' '.join(string_items)

    def items(self, **items):
        self.info(self.stringify_items(**items))

    def success(self, message, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['isSuccess'] = True
        super(AppLogger, self).info(message, *args, **kwargs)
