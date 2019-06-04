import logging
import traceback
import sys

from instattack.config import settings, config

from .handlers import SIMPLE_SYNC_HANDLERS, SYNC_HANDLERS
from .mixins import LoggerMixin


for level in settings.LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


_enabled = True


class SimpleSyncLogger(LoggerMixin, logging.Logger):

    __handlers__ = SIMPLE_SYNC_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)

        for handler in self.__handlers__:
            self.addHandler(handler)

        # level = config['log.logging']['level'].upper()
        # self.setLevel(level)

    def _log(self, *args, **kwargs):
        global _enabled
        if _enabled:
            return super(SimpleSyncLogger, self)._log(*args, **kwargs)


class SyncLogger(SimpleSyncLogger):

    __handlers__ = SYNC_HANDLERS

    def __init__(self, name, subname=None):
        super(SyncLogger, self).__init__(name)
        self.subname = subname

        # level = config['log.logging']['level'].upper()
        # self.setLevel(level)

    def traceback(self, *exc_info):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        self.error(exc_info[1])

        sys.stderr.write("\n")
        traceback.print_exception(*exc_info, limit=None, file=sys.stderr)


if settings.SIMPLE_LOGGER:
    logging.setLoggerClass(SimpleSyncLogger)
else:
    logging.setLoggerClass(SyncLogger)


def disable():
    global _enabled
    _enabled = False


def enable():
    global _enabled
    _enabled = True


def setLevel(level):
    root = logging.getLogger()
    root.setLevel(level.upper())


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


def get(name, subname=None):
    logger = logging.getLogger(name=name)
    if not settings.SIMPLE_LOGGER:
        logger.subname = subname
    return logger
