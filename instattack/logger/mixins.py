import contextlib
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

    def simple(self, msg, color=None, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra'].update({
            'color': color,
            'simple': True,
        })
        self._log(LoggingLevels.INFO.num, msg, args, **kwargs)

    def bare(self, msg, color='darkgray', *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra'].update({'color': color, 'bare': True})
        self._log(LoggingLevels.INFO.num, msg, args, **kwargs)

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
        self.line_index = 0
        sys.stdout.write('\n')

    def after_lines(self):
        # TODO: Make Header Log Component
        sys.stdout.write('\n')
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


class AsyncCustomLevelMixin(SyncCustomLevelMixin):

    def success(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    def start(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.START.num, msg, args, **kwargs)

    def stop(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.STOP.num, msg, args, **kwargs)

    def complete(self, msg, *args, **kwargs):
        return self._make_log_task(LoggingLevels.COMPLETE.num, msg, args, **kwargs)

    def bare(self, msg, color='darkgray', *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra'].update({'color': color, 'bare': True})
        return self._make_log_task(LoggingLevels.INFO.num, msg, args, **kwargs)

    @contextlib.asynccontextmanager
    async def logging_lines(self):
        try:
            await self.before_lines()
            yield self
        finally:
            await self.after_lines()

    async def before_lines(self):
        # TODO: Make Header Log Component
        sys.stdout.write('\n')
        self.line_index = 0
        sys.stdout.write('\n')

    async def after_lines(self):
        # TODO: Make Header Log Component
        sys.stdout.write('\n')
        self.line_index = 0
        sys.stdout.write('\n')

    async def line(self, item, color='darkgray', numbered=True):
        extra = {}
        if numbered:
            extra = {'line_index': self.line_index + 1}
            self.line_index += 1
        self.bare(item, color=color, extra=extra)

    async def line_by_line(self, lines, color='darkgray', numbered=True):
        async with self.logging_lines():
            for line in lines:
                await self.line(line, color=color, numbered=numbered)


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
        if 'LEVEL' in os.environ and not self.level:
            level = LoggingLevels[os.environ['LEVEL']]

            self.warning(f'Setting {self.name} Logger Level After Import...')
            self.setLevel(level.num)
