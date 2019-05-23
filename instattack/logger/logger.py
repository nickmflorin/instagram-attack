import aiologger
import logging
import os
import sys
import traceback

from .constants import LoggingLevels
from .handlers import (
    SIMPLE_SYNC_HANDLERS, SYNC_HANDLERS, SIMPLE_ASYNC_HANDLERS, ASYNC_HANDLERS)
from .mixins import SyncCustomLevelMixin, AsyncCustomLevelMixin, LoggerMixin


for level in LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


class SimpleSyncLogger(logging.Logger, LoggerMixin, SyncCustomLevelMixin):

    __handlers__ = SIMPLE_SYNC_HANDLERS

    def __init__(self, name):
        logging.Logger.__init__(self, name)

        self._conditional = None
        self.line_index = 0

        for handler in self.__handlers__:
            self.addHandler(handler)

        if 'LEVEL' in os.environ:
            level = LoggingLevels[os.environ['LEVEL']]
            self.setLevel(level.num)

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


class SimpleAsyncLogger(aiologger.Logger, LoggerMixin, AsyncCustomLevelMixin):

    __handlers__ = SIMPLE_ASYNC_HANDLERS

    def __init__(self, name):
        aiologger.Logger.__init__(self, name=name)

        self._conditional = None
        self.line_index = 0

        for handler in self.__handlers__:
            self.addHandler(handler)

        if 'LEVEL' in os.environ:
            level = LoggingLevels[os.environ['LEVEL']]
            self.setLevel(level.num)

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
            sinfo = None
            if logging._srcfile and caller is None:  # type: ignore
                # IronPython doesn't track Python frames, so findCaller raises an
                # exception on some versions of IronPython. We trap it here so that
                # IronPython can use logging.
                try:
                    fn, lno, func, sinfo = self.findCaller(stack_info)
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
            sinfo = None
            if logging._srcfile and caller is None:  # type: ignore
                # IronPython doesn't track Python frames, so findCaller raises an
                # exception on some versions of IronPython. We trap it here so that
                # IronPython can use logging.
                try:
                    fn, lno, func, sinfo = self.findCaller(stack_info)
                except ValueError:  # pragma: no cover
                    fn, lno, func = "(unknown file)", 0, "(unknown function)"
            elif caller:
                fn, lno, func, sinfo = caller
            else:  # pragma: no cover
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
            if exc_info and isinstance(exc_info, BaseException):
                exc_info = (type(exc_info), exc_info, exc_info.__traceback__)

            record = logging.LogRecord(
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

            # For whatever reason, when using our custom log levels, the arguments
            # in extra are not assigned to the record.
            if extra:
                for key, val in extra.items():
                    setattr(record, key, val)

            setattr(record, 'subname', self.subname)  # Reason We Override
            await self.handle(record)
