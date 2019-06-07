import curses
import logging
import sys
import traceback

from instattack.config import constants

from .mixins import LoggerMixin
from .diagnostics.panels import ApplicationPanel, StatsPanel
from .handlers import SIMPLE_HANDLERS, ARTSY_HANDLERS, DiagnosticsHandler


for level in constants.LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


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


class DiagnosticsLogger(ArtsyLogger):

    def __init__(self, name):
        super(DiagnosticsLogger, self).__init__(name)


loggers = {
    'diagnostics': DiagnosticsLogger,
    'artsy': ArtsyLogger,
    'simple': SimpleLogger
}

# TODO: We eventually want the logging mode to be a configuration constant,
# but that becomes difficult with the timing of file imports and loading of
# config file.
loggerClass = loggers[constants.LOGGER_MODE]
logging.setLoggerClass(loggerClass)


_enabled = True
_config = None
_app_panel = None
_stats_panel = None


def get(name, subname=None):
    logger = logging.getLogger(name=name)
    logger.subname = subname
    return logger


def configureLogLevel():
    global _config

    level = _config['instattack']['log.logging']['level']
    root = logging.getLogger()
    root.setLevel(level.upper())


def disable():
    global _enabled
    _enabled = False


def enable():
    global _enabled
    _enabled = True


def configure(config):

    global _config
    _config = config

    configureLogLevel()

    if constants.LOGGER_MODE == 'diagnostics':
        raise NotImplementedError("Not Supporting Diagnostics View Yet")

        curses.wrapper(draw_panels)

        diag_handler1 = DiagnosticsHandler(_app_panel.window)
        diag_handler2 = DiagnosticsHandler(_stats_panel.window)

        root = logging.getLogger()
        root.addHandler(diag_handler1)
        root.addHandler(diag_handler2)


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


def draw_panels(stdscr):
    # Not Implemented Yet
    stdscr.clear()
    stdscr.addstr(10, 10, 'Test Title')

    global _app_panel
    _app_panel = ApplicationPanel(stdscr)

    global _stats_panel
    _stats_panel = StatsPanel(stdscr)

    stdscr.refresh()
