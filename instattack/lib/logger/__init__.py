import logging
import aiologger

import inspect
import os
import sys
import traceback

from instattack.config import settings, config

from .mixins import SyncLoggerMixin, AsyncLoggerMixin

from .handlers import (
    SIMPLE_SYNC_HANDLERS,
    SYNC_HANDLERS,
    SIMPLE_ASYNC_HANDLERS,
    ASYNC_HANDLERS
)


for level in settings.LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


_enabled = True


def disable():
    global _enabled
    _enabled = False


def enable():
    global _enabled
    _enabled = True


def disable_external_loggers(*args):
    for module in args:
        external_logger = logging.getLogger(module)
        external_logger.setLevel(logging.CRITICAL)


def get_async(name, subname=None):
    if settings.SIMPLE_LOGGER:
        return SimpleAsyncLogger(name)
    return AsyncLogger(name, subname=subname)


def get_sync(name, subname=None):
    if settings.SIMPLE_LOGGER:
        return SimpleSyncLogger(name)
    return SyncLogger(name, subname=subname)


class LoggerMixin(object):

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


class SimpleSyncLogger(LoggerMixin, SyncLoggerMixin, logging.Logger):

    __handlers__ = SIMPLE_SYNC_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)

        for handler in self.__handlers__:
            self.addHandler(handler)

        level = config['log.logging']['level'].upper()
        self.setLevel(level)

    def _log(self, *args, **kwargs):
        global _enabled
        if _enabled:
            return super(SimpleSyncLogger, self)._log(*args, **kwargs)


class SyncLogger(SimpleSyncLogger):

    __handlers__ = SYNC_HANDLERS

    def __init__(self, name, subname=None):
        super(SyncLogger, self).__init__(name)
        self.subname = subname

    def traceback(self, *exc_info):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        self.error(exc_info[1])

        sys.stderr.write("\n")
        traceback.print_exception(*exc_info, limit=None, file=sys.stderr)


class SimpleAsyncLogger(LoggerMixin, AsyncLoggerMixin, aiologger.Logger):

    __handlers__ = SIMPLE_ASYNC_HANDLERS

    def __init__(self, name):
        super(SimpleAsyncLogger, self).__init__(name=name)

        for handler in self.__handlers__:
            self.addHandler(handler)

        level = config['log.logging']['level'].upper()
        self.setLevel(level)

    async def shutdown(self):
        """
        This does not seem to be working properly...
        """
        for handler in self.handlers:
            await handler.flush()
            await handler.close()
        await super(SimpleAsyncLogger, self).shutdown()

    # async def _create_record(self, level, msg, args, caller=None, **kwargs):
    #     """
    #     This is the majority of AIOLogger's _log() method, but we separate it out
    #     so we can more easily override their _log method.
    #     """
    #     sinfo = None
    #     if logging._srcfile and caller is None:
    #         try:
    #             fn, lno, func, sinfo = self.findCaller()
    #         except ValueError:
    #             fn, lno, func = "(unknown file)", 0, "(unknown function)"
    #     elif caller:
    #         fn, lno, func, sinfo = caller
    #     else:
    #         fn, lno, func = "(unknown file)", 0, "(unknown function)"

    #     kwargs.update(
    #         pathname=fn,
    #         lineno=lno,
    #         func=func,
    #         sinfo=sinfo,
    #     )

    #     kwargs.setdefault('exc_info', None)
    #     if kwargs.get('exc_info') and isinstance(kwargs['exc_info'], BaseException):
    #         kwargs['exc_info'] = (
    #             type(kwargs['exc_info']),
    #             kwargs['exc_info'],
    #             kwargs['exc_info'].__traceback__
    #         )

    #     return logging.LogRecord(
    #         name=self.name,
    #         level=level,
    #         msg=msg,
    #         args=args,
    #         **kwargs,
    #     )
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

    async def _log(self, level, msg, args, **kwargs):
        global _enabled
        if _enabled:
            record = await self._create_record(level, msg, args, **kwargs)
            await self.handle(record)


class AsyncLogger(SimpleAsyncLogger):

    __handlers__ = ASYNC_HANDLERS

    def __init__(self, name, subname=None):
        super(AsyncLogger, self).__init__(name)
        self.subname = subname

    # async def _log(self, level, msg, args, extra=None, **kwargs):
    #     global _enabled
    #     if _enabled:
    #         record = await self._create_record(level, msg, args, extra=extra, **kwargs)

    #         # For whatever reason, when using our custom log levels, the arguments
    #         # in extra are not assigned to the record.
    #         if extra:
    #             for key, val in extra.items():
    #                 setattr(record, key, val)

    #         if self.subname is not None:
    #             setattr(record, 'subname', self.subname)
    #         await self.handle(record)
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
