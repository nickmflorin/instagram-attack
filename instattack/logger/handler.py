import aiologger
import logging
import sys

from artsylogger import ArtsyHandlerMixin

from instattack.conf.utils import relative_to_root
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


class CustomHandlerMixin(ArtsyHandlerMixin):

    def prepare_record(self, record):
        super(CustomHandlerMixin, self).prepare_record(record)

        self.default(record, 'is_exception', default=False)

        if not getattr(record, 'level', None):
            setattr(record, 'level', LoggingLevels[record.levelname])

        if isinstance(record.msg, Exception):
            record.is_exception = True

        record.pathname = relative_to_root(record.pathname)


class SyncHandler(logging.StreamHandler, CustomHandlerMixin):

    def __init__(self, filter=None, format_string=None):
        super(SyncHandler, self).__init__(stream=sys.stderr)

        self.useArtsyFormatter(format_string=format_string)
        if filter:
            self.addFilter(filter)

    def emit(self, record):
        self.prepare_record(record)
        super(SyncHandler, self).emit(record)


class AsyncHandler(aiologger.handlers.AsyncStreamHandler, CustomHandlerMixin):

    def __init__(self, filter=None, format_string=None):
        """
        Initialise an instance, using the passed queue.
        """
        super(AsyncHandler, self).__init__(
            stream=sys.stderr,
            filter=filter,
        )
        self.useArtsyFormatter(format_string=format_string)

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
