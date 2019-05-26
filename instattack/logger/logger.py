import aiologger
import contextlib
import logging
import inspect
import os
import sys
import traceback

from .utils import is_log_file
from .constants import LoggingLevels
from .handlers import (
    SIMPLE_SYNC_HANDLERS, SYNC_HANDLERS, SIMPLE_ASYNC_HANDLERS, ASYNC_HANDLERS)


for level in LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


class LoggerMixin(object):

    def init(self):

        self._conditional = None
        self.line_index = 0

        for handler in self.__handlers__:
            self.addHandler(handler)

        if 'LEVEL' in os.environ:
            self.updateLevel()

    def findCaller(self, *args):
        """
        Find the stack frame of the caller so that we can note the source
        file name, line number and function name.

        Overridden to exclude our logging module files.
        """
        f = inspect.currentframe()
        rv = "(unknown file)", 0, "(unknown function)"
        while hasattr(f, "f_code"):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)

            if filename == logging._srcfile:
                f = f.f_back
                continue

            elif is_log_file(filename):
                f = f.f_back
                continue

            # We automatically set sininfo to None since we do not know where
            # that is coming from and the original method expects a 4-tuple to
            # return.
            rv = (co.co_filename, f.f_lineno, co.co_name, None)
            break
        return rv

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
        if 'LEVEL' in os.environ:
            level = LoggingLevels[os.environ['LEVEL']]
            self.setLevel(level.num)


class SyncLoggerMixin(LoggerMixin):

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
        self.line_index = 0
        try:
            sys.stdout.write('\n')
            yield self
        finally:
            sys.stdout.write('\n')
            self.line_index = 0

    def line(self, item, color='darkgray'):
        self.bare(item, color=color, extra={'line_index': self.line_index + 1})
        self.line_index += 1

    def line_by_line(self, lines, color='darkgray'):
        with self.logging_lines():
            [self.line(line, color=color) for line in lines]


class AsyncLoggerMixin(SyncLoggerMixin):

    async def success(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['frame_correction'] = 1
        return await self._log(LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    async def start(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['frame_correction'] = 1
        return await self._log(LoggingLevels.START.num, msg, args, **kwargs)

    async def stop(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['frame_correction'] = 1
        return await self._log(LoggingLevels.STOP.num, msg, args, **kwargs)

    async def complete(self, msg, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['frame_correction'] = 1
        return await self._log(LoggingLevels.COMPLETE.num, msg, args, **kwargs)

    async def bare(self, msg, color='darkgray', *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra'].update({'color': color, 'bare': True})
        return await self._log(LoggingLevels.INFO.num, msg, args, **kwargs)

    @contextlib.asynccontextmanager
    async def logging_lines(self):
        self.line_index = 0
        try:
            sys.stdout.write('\n')
            yield self
        finally:
            sys.stdout.write('\n')
            self.line_index = 0

    async def line(self, item, color='darkgray'):
        await self.bare(item, color=color, extra={'line_index': self.line_index + 1})
        self.line_index += 1

    async def line_by_line(self, lines, color='darkgray'):
        async with self.logging_lines():
            [await self.line(line, color=color) for line in lines]


class SimpleSyncLogger(SyncLoggerMixin, logging.Logger):

    __handlers__ = SIMPLE_SYNC_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)
        self.init()

    def _log(self, *args, **kwargs):
        if not self.conditionally_disabled:  # Reason We Override
            super(SimpleSyncLogger, self)._log(*args, **kwargs)


class SyncLogger(SimpleSyncLogger):

    __handlers__ = SYNC_HANDLERS

    def __init__(self, name, subname=None):
        super(SyncLogger, self).__init__(name)
        self.subname = subname

    def traceback(self, *exc_info, extra=None):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        extra = extra or {}
        extra.update({
            'header_label': "Error",
            'header_formatter': (
                LoggingLevels.ERROR.format.without_text_decoration().without_wrapping()),
        })
        self.error(exc_info[1], extra=extra)

        sys.stderr.write("\n")
        traceback.print_exception(*exc_info, limit=None, file=sys.stderr)


class SimpleAsyncLogger(AsyncLoggerMixin, aiologger.Logger):

    __handlers__ = SIMPLE_ASYNC_HANDLERS

    def __init__(self, name):
        super(SimpleAsyncLogger, self).__init__(name=name)
        self.init()

    async def _create_record(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        caller=None,
    ):
        """
        This is the majority of AIOLogger's _log() method, but we separate it out
        so we can more easily override their _log method.
        """
        sinfo = None
        if logging._srcfile and caller is None:  # type: ignore
            try:
                fn, lno, func, sinfo = self.findCaller()
            except ValueError:  # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        elif caller:
            fn, lno, func, sinfo = caller
        else:  # pragma: no cover
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info and isinstance(exc_info, BaseException):
            exc_info = (type(exc_info), exc_info, exc_info.__traceback__)

        return logging.LogRecord(
            name=self.name,
            level=level,
            pathname=fn,
            lineno=lno,
            msg=msg,
            args=args,
            exc_info=exc_info,
            func=func,
            sinfo=sinfo,
            extra=extra,
        )

    async def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        caller=None,
    ):

        # Until we come up with a better way of ensuring ths LEVEL in os.environ
        # before loggers are imported - this will at least make sure the level
        # is always right.
        self.updateLevel()

        if not self.conditionally_disabled:  # Reason We Override
            record = await self._create_record(
                level,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                caller=caller,
            )
            await self.handle(record)


class AsyncLogger(SimpleAsyncLogger):

    __handlers__ = ASYNC_HANDLERS

    def __init__(self, name, subname=None):
        super(AsyncLogger, self).__init__(name)
        self.subname = subname

    async def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        caller=None,
    ):
        # Until we come up with a better way of ensuring ths LEVEL in os.environ
        # before loggers are imported - this will at least make sure the level
        # is always right.
        self.updateLevel()

        if not self.conditionally_disabled:  # Reason We Override
            record = await self._create_record(
                level,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                caller=caller,
            )

            # For whatever reason, when using our custom log levels, the arguments
            # in extra are not assigned to the record.
            if extra:
                for key, val in extra.items():
                    setattr(record, key, val)

            if self.subname is not None:
                setattr(record, 'subname', self.subname)  # Reason We Override
            await self.handle(record)
