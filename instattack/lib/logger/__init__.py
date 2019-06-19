import logging

from instattack.config import constants

from .loggers import SimpleLogger, TermxLogger, DiagnosticsLogger
from .handlers import DiagnosticsHandler
from .formats import SIMPLE_FORMAT_STRING


_enabled = True


loggers = {
    'diagnostics': DiagnosticsLogger,
    'termx': TermxLogger,
    'simple': SimpleLogger
}


def configure(level=None, mode=None):
    """
    Set the default logging class based on the default mode until one is configured
    from the parsed command line arguments by the base controller.
    """
    root = logging.getLogger()
    if level:
        root.setLevel(level.upper())
    if mode:
        logging.setLoggerClass(loggers[mode])


loggerClass = configure(mode=constants.DEFAULT_LOGGER_MODE)


def configure_diagnostics(window):
    """
    [x] TODO:
    --------
    Make sure the loggerClass is the diagnostics logger.

    We cannot use the ArtsyLogger format strings for now, until they are
    capable of being formatted with curses support.
    """
    handler = DiagnosticsHandler(window, formatter=SIMPLE_FORMAT_STRING)
    root = logging.getLogger()
    root.addHandler(handler)


def disable():
    global _enabled
    _enabled = False


def enable():
    global _enabled
    _enabled = True


class DisableLogger():

    def __enter__(self):
        disable()

    def __exit__(self, a, b, c):
        enable()


def get(name, subname=None):
    logger = logging.getLogger(name=name)
    logger.subname = subname
    return logger


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)
