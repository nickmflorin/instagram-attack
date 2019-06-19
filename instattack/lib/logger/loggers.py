import logging
import inspect
import os
import sys
import traceback

from .handlers import SIMPLE_HANDLERS, TERMX_HANDLERS


class SimpleLogger(logging.Logger):

    __handlers__ = SIMPLE_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)
        self.subname = None

        for handler in self.__handlers__:
            self.addHandler(handler)

    def _log(self, *args, **kwargs):
        from . import _enabled
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
