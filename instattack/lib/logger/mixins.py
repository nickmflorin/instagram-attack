import inspect
import logging
import os
import sys
import traceback

from instattack.config import settings

from .handlers import SIMPLE_SYNC_HANDLERS, SYNC_HANDLERS


class LoggerMixin(object):

    def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.SUCCESS.num):
            self._log(settings.LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    def start(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.START.num):
            self._log(settings.LoggingLevels.START.num, msg, args, **kwargs)

    def stop(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.STOP.num):
            self._log(settings.LoggingLevels.STOP.num, msg, args, **kwargs)

    def complete(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.COMPLETE.num):
            self._log(settings.LoggingLevels.COMPLETE.num, msg, args, **kwargs)

    def simple(self, msg, color=None, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra'].update({
            'color': color,
            'simple': True,
        })
        self._log(settings.LoggingLevels.INFO.num, msg, args, **kwargs)

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
