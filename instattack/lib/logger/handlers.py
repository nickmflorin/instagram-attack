import logging
import sys

from artsylogger import ArtsyHandlerMixin

from instattack.config import settings
from instattack.lib.utils import relative_to_root

from .formats import (
    SIMPLE_FORMATTER, LOG_FORMAT_STRING, BARE_FORMAT_STRING, SIMPLE_FORMAT_STRING)


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


class SyncHandler(SimpleSyncHandler, CustomHandlerMixin):

    def __init__(self, filter=None, format_string=None):
        super(SyncHandler, self).__init__(filter=filter)
        self.useArtsyFormatter(format_string=format_string)

    def emit(self, record):
        self.prepare_record(record)
        super(SyncHandler, self).emit(record)


SIMPLE_SYNC_HANDLERS = [
    SimpleSyncHandler(
        formatter=SIMPLE_FORMATTER,
        filter=TypeFilter(require=['bare']),
    ),
    SimpleSyncHandler(
        formatter=SIMPLE_FORMATTER,
        filter=TypeFilter(require=['simple']),
    ),
    SimpleSyncHandler(
        formatter=SIMPLE_FORMATTER,
        filter=TypeFilter(disallow=['bare', 'simple'])
    ),
]


SYNC_HANDLERS = [
    SyncHandler(
        format_string=BARE_FORMAT_STRING,
        filter=TypeFilter(require=['bare']),
    ),
    SyncHandler(
        format_string=SIMPLE_FORMAT_STRING,
        filter=TypeFilter(require=['simple']),
    ),
    SyncHandler(
        format_string=LOG_FORMAT_STRING,
        filter=TypeFilter(disallow=['bare', 'simple'])
    ),
]
