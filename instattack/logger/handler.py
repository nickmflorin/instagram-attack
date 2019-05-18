import aiologger
import logging
from plumbum import colors
import sys

from .constants import LoggingLevels


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


class CustomFormatter(logging.Handler):

    def __init__(self, format_string=None, **kwargs):
        super(CustomFormatter, self).__init__(**kwargs)
        self.format_string = format_string

    def format(self, record):
        format_string = self.format_string(record)
        return format_string.format(record)


class HandlerMixin(object):

    def default(self, record, attr, default=None):
        setattr(record, attr, getattr(record, attr, default))

    def prepare_record(self, record):

        self.default(record, 'level_format')
        self.default(record, 'line_index')
        self.default(record, 'show_level', default=True)
        self.default(record, 'highlight', default=False)
        self.default(record, 'color')
        self.default(record, 'is_exception', default=False)

        if not getattr(record, 'level', None):
            setattr(record, 'level', LoggingLevels[record.levelname])

        if isinstance(record.msg, Exception):
            record.is_exception = True

        if record.color:
            if isinstance(record.color, str):
                setattr(record, 'color', colors.fg(record.color))


class SyncHandler(logging.StreamHandler, HandlerMixin):

    def __init__(self, filter=None, format_string=None):
        super(SyncHandler, self).__init__(
            stream=sys.stderr,
        )

        formatter = CustomFormatter(format_string=format_string)
        self.setFormatter(formatter)

        if filter:
            self.addFilter(filter)

    def emit(self, record):
        self.prepare_record(record)
        super(SyncHandler, self).emit(record)


class AsyncHandler(aiologger.handlers.AsyncStreamHandler, HandlerMixin):

    def __init__(self, filter=None, format_string=None):
        """
        Initialise an instance, using the passed queue.
        """
        super(AsyncHandler, self).__init__(
            stream=sys.stderr,
            formatter=CustomFormatter(format_string=format_string),
            filter=filter,
        )

    async def emit(self, record):
        """
        Prepares a record for queuing. The object returned by this method is
        enqueued.

        The base implementation formats the record to merge the message
        and arguments, and removes unpickleable items from the record
        in-place.

        You might want to override this method if you want to convert
        the record to a dict or JSON string, or send a modified copy
        of the record while leaving the original intact.
        """
        self.prepare_record(record)

        if self.writer is None:
            self.writer = await self._init_writer()

        try:
            msg = self.format(record) + self.terminator

            self.writer.write(msg.encode())
            await self.writer.drain()
        except Exception:
            await self.handleError(record)
