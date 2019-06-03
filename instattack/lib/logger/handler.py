import aiologger
import logging
import sys

from artsylogger import ArtsyHandlerMixin

from instattack.config import settings
from instattack.lib.utils import relative_to_root


class CustomHandlerMixin(ArtsyHandlerMixin):

    def prepare_record(self, record):
        super(CustomHandlerMixin, self).prepare_record(record)

        self.default(record, 'is_exception', default=False)

        if not getattr(record, 'level', None):
            setattr(record, 'level', settings.LoggingLevels[record.levelname])

        if isinstance(record.msg, Exception):
            record.is_exception = True

        record.pathname = relative_to_root(record.pathname)


class SimpleSyncHandler(logging.StreamHandler):

    def __init__(self, filter=None, formatter=None):
        super(SimpleSyncHandler, self).__init__(stream=sys.stderr)

        if formatter:
            self.setFormatter(formatter)
        if filter:
            self.addFilter(filter)


class SimpleAsyncHandler(aiologger.handlers.AsyncStreamHandler):
    def __init__(self, filter=None, formatter=None):
        super(SimpleAsyncHandler, self).__init__(
            stream=sys.stderr,
            filter=filter,
        )
        if formatter:
            self.setFormatter(formatter)


class SyncHandler(SimpleSyncHandler, CustomHandlerMixin):

    def __init__(self, filter=None, format_string=None):
        super(SyncHandler, self).__init__(filter=filter)
        self.useArtsyFormatter(format_string=format_string)

    def emit(self, record):
        self.prepare_record(record)
        super(SyncHandler, self).emit(record)


class AsyncHandler(SimpleAsyncHandler, CustomHandlerMixin):

    def __init__(self, filter=None, format_string=None):
        """
        Initialise an instance, using the passed queue.
        """
        super(AsyncHandler, self).__init__(filter=filter)
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
