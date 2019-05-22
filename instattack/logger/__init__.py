from instattack.conf import settings

from .utils import Format  # noqa
from .logger import AsyncLogger, SyncLogger, SimpleAsyncLogger, SimpleSyncLogger
from .setup import *  # noqa


def get_async(name, subname=None):
    if settings.SIMPLE_LOGGER:
        return SimpleAsyncLogger(name)

    return AsyncLogger(name, subname=subname)


def get_sync(name, subname=None):

    if settings.SIMPLE_LOGGER:
        return SimpleSyncLogger(name)

    return SyncLogger(name, subname=subname)
