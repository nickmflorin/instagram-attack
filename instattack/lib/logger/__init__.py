import logging
import sys
import traceback

from instattack.config import constants

from .mixins import LoggerMixin
from .handlers import SIMPLE_HANDLERS, ARTSY_HANDLERS, DiagnosticsHandler
from .formats import LOG_FORMAT_STRING, SIMPLE_FORMAT_STRING


_enabled = True
_config = None


def disable():
    global _enabled
    _enabled = False


def enable():
    global _enabled
    _enabled = True


for level in constants.LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


def get(name, subname=None):
    logger = logging.getLogger(name=name)
    logger.subname = subname
    return logger


def configure_diagnostics(window):
    if constants.LOGGER_MODE != 'diagnostics':
        raise RuntimeError('Invalid configuration.')

    logging.setLoggerClass(DiagnosticsLogger)

    # We cannot use the ArtsyLogger format strings for now, until they are
    # capable of being formatted with curses support.
    handler = DiagnosticsHandler(window, formatter=SIMPLE_FORMAT_STRING)
    root = logging.getLogger()
    root.addHandler(handler)


def configure(config):

    global _config

    level = _config['instattack']['log.logging']['level']
    root = logging.getLogger()
    root.setLevel(level.upper())


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


class SimpleLogger(LoggerMixin, logging.Logger):

    __handlers__ = SIMPLE_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)
        self.subname = None

        for handler in self.__handlers__:
            self.addHandler(handler)

    def _log(self, *args, **kwargs):
        global _enabled
        if _enabled:
            return super(SimpleLogger, self)._log(*args, **kwargs)


class ArtsyLogger(SimpleLogger):

    __handlers__ = ARTSY_HANDLERS

    def traceback(self, *exc_info):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        self.error(exc_info[1])

        sys.stderr.write("\n")
        traceback.print_exception(*exc_info, limit=None, file=sys.stderr)


class DiagnosticsLogger(SimpleLogger):
    """
    We cannot use ArtsyLogger right now because those UNICODE formats do not
    display nicely with curses.

    Handlers have to be dynamically created based on the curses window or panel
    objects.

    [x] IMPORTANT:
    -------------
    Right now, the only importance of the DiagnosticsLogger is that it does
    not have any handlers, which means that the other handlers will not be
    used simultaneously when it is initialized for a given window.
    """
    __handlers__ = []

    def __init__(self, name):
        super(DiagnosticsLogger, self).__init__(name)


loggers = {
    'diagnostics': DiagnosticsLogger,
    'artsy': ArtsyLogger,
    'simple': SimpleLogger
}

# [x] TODO:
# We eventually want the logging mode to be a configuration constant,
# but that becomes difficult with the timing of file imports and loading of
# config file.
loggerClass = loggers[constants.LOGGER_MODE]
logging.setLoggerClass(loggerClass)
