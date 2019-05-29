from .filters import TypeFilter
from .handler import AsyncHandler, SyncHandler, SimpleSyncHandler, SimpleAsyncHandler
from .log_formats import (
    SIMPLE_FORMATTER, LOG_FORMAT_STRING, BARE_FORMAT_STRING, SIMPLE_FORMAT_STRING)


SIMPLE_ASYNC_HANDLERS = [
    SimpleAsyncHandler(
        formatter=SIMPLE_FORMATTER,
        filter=TypeFilter(require=['bare']),
    ),
    SimpleAsyncHandler(
        formatter=SIMPLE_FORMATTER,
        filter=TypeFilter(require=['simple']),
    ),
    SimpleAsyncHandler(
        formatter=SIMPLE_FORMATTER,
        filter=TypeFilter(disallow=['bare', 'simple'])
    ),
]

ASYNC_HANDLERS = [
    AsyncHandler(
        format_string=BARE_FORMAT_STRING,
        filter=TypeFilter(require=['bare']),
    ),
    AsyncHandler(
        format_string=SIMPLE_FORMAT_STRING,
        filter=TypeFilter(require=['simple']),
    ),
    AsyncHandler(
        format_string=LOG_FORMAT_STRING,
        filter=TypeFilter(disallow=['bare', 'simple'])
    ),
]

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
