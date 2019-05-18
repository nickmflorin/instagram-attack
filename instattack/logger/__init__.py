from .utils import Format  # noqa
from .logger import AsyncLogger, SyncLogger
from .setup import *  # noqa


def get_async(name, subname=None):
    logger = AsyncLogger(name, subname=subname)
    return logger


def get_sync(name, subname=None):
    logger = SyncLogger(name, subname=subname)
    return logger
