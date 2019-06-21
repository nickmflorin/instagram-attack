import contextlib
import logging

from instattack.config import constants

from .loggers import SimpleLogger, TermxLogger, DiagnosticsLogger
from .handlers import DiagnosticsHandler
from .formats import SIMPLE_FORMAT_STRING


class _Logger(dict):

    __LOGGERS__ = {
        'diagnostics': DiagnosticsLogger,
        'termx': TermxLogger,
        'simple': SimpleLogger
    }

    def __init__(self, data):
        super(_Logger, self).__init__(data)
        self.enabled = True
        self.configure(mode=constants.DEFAULT_LOGGER_MODE)

    def get(self, name, subname=None):
        logger = logging.getLogger(name=name)
        logger.subname = subname
        return logger

    def configure(self, level=None, mode=None):
        """
        Set the default logging class based on the default mode until one is configured
        from the parsed command line arguments by the base controller.
        """
        root = logging.getLogger()
        if level:
            root.setLevel(level.upper())
        if mode:
            logging.setLoggerClass(self.__LOGGERS__[mode])

    def configure_diagnostics(self, window):
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

    def disable(self):
        self.enabled = False

    def enable(self):
        self.enabled = True

    @contextlib.contextmanager
    def DisableLogger(self):
        self.disable()
        try:
            yield self
        finally:
            self.enable()

    @classmethod
    def disable_external_loggers(cls, *args):
        for module in args:
            external_logger = logging.getLogger(module)
            external_logger.setLevel(logging.CRITICAL)


logger = _Logger({})
