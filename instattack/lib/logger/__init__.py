import logging
import inspect
import os
import sys
import traceback

from instattack.config import constants

from .handlers import SIMPLE_HANDLERS, TERMX_HANDLERS, DiagnosticsHandler
from .formats import TERMX_FORMAT_STRING, SIMPLE_FORMAT_STRING


_enabled = True


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

    level = config['instattack']['log.logging']['level']
    root = logging.getLogger()
    root.setLevel(level.upper())


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


class SimpleLogger(logging.Logger):

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

    def traceback(self, *exc_info):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        sys.stderr.write("\n")
        self.error(exc_info[1])

        sys.stderr.write("\n")
        traceback.print_exception(*exc_info, limit=None, file=sys.stderr)

    def findCaller(self, *args):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.

        Overridden to exclude our logging module files.
        """
        from instattack.lib.utils import (
            is_log_file, is_site_package_file, is_app_file)

        f = inspect.currentframe()
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)

            if filename == logging._srcfile:
                f = f.f_back
                continue

            # TODO: Keep looking until file is inside app_root.
            elif is_log_file(filename):
                f = f.f_back
                continue

            elif is_site_package_file(filename):
                f = f.f_back
                continue

            elif not is_app_file(filename):
                f = f.f_back
                continue

            # We automatically set sininfo to None since we do not know where
            # that is coming from and the original method expects a 4-tuple to
            # return.
            rv = (co.co_filename, f.f_lineno, co.co_name, None)
            break
        return rv


class TermxLogger(SimpleLogger):

    __handlers__ = TERMX_HANDLERS


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
    'termx': TermxLogger,
    'simple': SimpleLogger
}

# [x] TODO:
# We eventually want the logging mode to be a configuration constant,
# but that becomes difficult with the timing of file imports and loading of
# config file.
loggerClass = loggers[constants.LOGGER_MODE]
logging.setLoggerClass(loggerClass)
