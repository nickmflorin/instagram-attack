import contextlib
import traceback
import os
import sys

from .constants import LoggingLevels


__all__ = (
    'SyncCustomLevelMixin',
    'AsyncCustomLevelMixin',
    'LoggerMixin',
)


class SyncCustomLevelMixin(object):

    def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(LoggingLevels.SUCCESS.num):
            self._log(LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    def start(self, msg, *args, **kwargs):
        if self.isEnabledFor(LoggingLevels.START.num):
            self._log(LoggingLevels.START.num, msg, args, **kwargs)

    def stop(self, msg, *args, **kwargs):
        if self.isEnabledFor(LoggingLevels.STOP.num):
            self._log(LoggingLevels.STOP.num, msg, args, **kwargs)

    def complete(self, msg, *args, **kwargs):
        if self.isEnabledFor(LoggingLevels.COMPLETE.num):
            self._log(LoggingLevels.COMPLETE.num, msg, args, **kwargs)

    def simple(self, msg, color=None, extra=None, *args, **kwargs):
        extra = extra or {}
        extra.update({
            'color': color,
            'simple': True,
        })
        self._log(LoggingLevels.INFO.num, msg, args, extra=extra, **kwargs)

    def bare(self, msg, color='darkgray', extra=None, *args, **kwargs):
        extra = extra or {}
        extra.update({
            'color': color,
            'bare': True,
        })
        self._log(LoggingLevels.INFO.num, msg, args, extra=extra, **kwargs)

    @contextlib.contextmanager
    def logging_lines(self):
        try:
            self.before_lines()
            yield self
        finally:
            self.after_lines()

    def before_lines(self):
        # TODO: Make Header Log Component
        sys.stdout.write('\n')
        sys.stdout.write("-------------------------------------\n")
        self.line_index = 0
        sys.stdout.write('\n')

    def after_lines(self):
        # TODO: Make Header Log Component
        sys.stdout.write('\n')
        sys.stdout.write("-------------------------------------\n")
        self.line_index = 0
        sys.stdout.write('\n')

    def line(self, item, color='darkgray', numbered=True):
        extra = {}
        if numbered:
            extra = {'line_index': self.line_index + 1}
            self.line_index += 1
        self.bare(item, color=color, extra=extra)

    def line_by_line(self, lines, color='darkgray', numbered=True):
        with self.logging_lines():
            for line in lines:
                self.line(line, color=color, numbered=numbered)


class AsyncCustomLevelMixin(object):

    def success(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    def start(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.START.num, msg, args, **kwargs)

    def stop(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.STOP.num, msg, args, **kwargs)

    def complete(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.COMPLETE.num, msg, args, **kwargs)


class LoggerMixin(object):

    def sublogger(self, subname):
        logger = self.__class__(self.name, subname=subname)
        return logger

    def disable_on_false(self, value):
        self._conditional = (value, False)

    def disable_on_true(self, value):
        self._conditional = (value, True)

    def condition_on_true(self, value, subname=None):
        logger = self.__class__(self.name, subname=subname)
        logger.disable_on_true(value)
        return logger

    def condition_on_false(self, value, subname=None):
        logger = self.__class__(self.name, subname=subname)
        logger.disable_on_false(value)
        return logger

    @property
    def conditionally_disabled(self):
        if self._conditional is not None:
            if self._conditional[0] == self._conditional[1]:
                return True
        return False

    def updateLevel(self):
        # Environment variable might not be set for usages of AppLogger
        # in __main__ module right away.
        if not os.environ.get('LEVEL'):
            raise RuntimeError('Level is not in the environment variables.')
        self.setLevel(os.environ['LEVEL'])

    def traceback(self, ex, raw=False):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        formatter = LoggingLevels.ERROR.format.without_text_decoration().without_wrapping()
        self.exception(ex, extra={
            'header_label': "Error",
            'header_formatter': formatter
        })
        sys.stderr.write("\n")
        traceback.print_exception(ex.__class__, ex, ex.__traceback__,
            limit=None, file=sys.stderr)
