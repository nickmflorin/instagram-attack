import aiologger
import logging
import inspect
import os
import sys
import traceback

from instattack.config import settings

from .utils import is_log_file, is_site_package_file
from .handlers import (
    SIMPLE_SYNC_HANDLERS, SYNC_HANDLERS, SIMPLE_ASYNC_HANDLERS, ASYNC_HANDLERS)


__all__ = (
    '_enabled',
    'enable',
    'disable',
    'SyncLogger',
    'SimpleAsyncLogger',
    'AsyncLogger',
    'SimpleSyncLogger',
)

_enabled = True


def disable():
    global _enabled
    _enabled = False


def enable():
    global _enabled
    _enabled = True


for level in settings.LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


class LoggerMixin(object):

    def init(self):
        self.line_index = 0

        # This is a TERRIBLE solution to an annoying problem, that is on the
        # backburner for now... We have had trouble preventing the import of any
        # file that would instantiate a Logger before we had a chance to set the
        # level from the CLI args in os.environ... So it is not always guaranteed
        # that the logger has access to os.environ['LEVEL'] on init.
        self._environ_level_set = False

        for handler in self.__handlers__:
            self.addHandler(handler)

        if os.environ.get('INSTATTACK_LOG_LEVEL'):

            level = os.environ['INSTATTACK_LOG_LEVEL']
            if not isinstance(level, str):
                raise RuntimeError('Invalid Level')

            self.setLevel(level)
            self._environ_level_set = True

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

            # TODO: Keep looking until file is inside app_root.
            elif is_log_file(filename):
                f = f.f_back
                continue

            elif is_site_package_file(filename):
                f = f.f_back
                continue

            # We automatically set sininfo to None since we do not know where
            # that is coming from and the original method expects a 4-tuple to
            # return.
            rv = (co.co_filename, f.f_lineno, co.co_name, None)
            break
        return rv


class SyncLoggerMixin(LoggerMixin):

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


class AsyncLoggerMixin(SyncLoggerMixin):

    async def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.SUCCESS.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.SUCCESS.num, msg, args, **kwargs)

    async def start(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.START.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.START.num, msg, args, **kwargs)

    async def stop(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.STOP.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.STOP.num, msg, args, **kwargs)

    async def complete(self, msg, *args, **kwargs):
        if self.isEnabledFor(settings.LoggingLevels.COMPLETE.num):
            kwargs.setdefault('extra', {})
            kwargs['extra']['frame_correction'] = 1
            return await self._log(settings.LoggingLevels.COMPLETE.num, msg, args, **kwargs)


class SimpleSyncLogger(SyncLoggerMixin, logging.Logger):

    __handlers__ = SIMPLE_SYNC_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)
        self.init()

    def _log(self, *args, **kwargs):
        global _enabled
        if _enabled:
            return super(SimpleSyncLogger, self)._log(*args, **kwargs)


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
        self.error(exc_info[1], extra=extra)

        sys.stderr.write("\n")
        traceback.print_exception(*exc_info, limit=None, file=sys.stderr)


class SimpleAsyncLogger(AsyncLoggerMixin, aiologger.Logger):

    __handlers__ = SIMPLE_ASYNC_HANDLERS

    def __init__(self, name):
        super(SimpleAsyncLogger, self).__init__(name=name)
        self.init()

    async def shutdown(self):
        for handler in self.handlers:
            await handler.flush()
            await handler.close()
        await super(SimpleAsyncLogger, self).shutdown()

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
        global _enabled
        if _enabled:
            # Until we come up with a better way of ensuring ths LEVEL in os.environ
            # before loggers are imported - this will at least make sure the level
            # is always right.
            if not self._environ_level_set:
                if os.environ.get('INSTATTACK_LOG_LEVEL'):
                    level = os.environ['INSTATTACK_LOG_LEVEL']
                    if not isinstance(level, str):
                        raise RuntimeError('Invalid Level')

                    self.setLevel(level)
                    self._environ_level_set = True

            # We used to override to check if conditionally_disabled was set here, but
            # maybe we don't need that anymore?
            # >>> if not self.conditionally_disabled:

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
        if not self._environ_level_set:
            if os.environ.get('INSTATTACK_LOG_LEVEL'):
                level = os.environ['INSTATTACK_LOG_LEVEL']
                if not isinstance(level, str):
                    raise RuntimeError('Invalid Level')

                self.setLevel(level)
                self._environ_level_set = True

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
