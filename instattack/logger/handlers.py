from .handler import AsyncHandler, SyncHandler, TypeFilter
from .log_formats import (
    LOG_FORMAT_STRING, BARE_FORMAT_STRING, SIMPLE_FORMAT_STRING)


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
