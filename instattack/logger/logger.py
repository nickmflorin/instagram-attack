import aiologger
import logging
import os

from .constants import LoggingLevels
from .handlers import SYNC_HANDLERS, ASYNC_HANDLERS
from .mixins import SyncCustomLevelMixin, AsyncCustomLevelMixin, LoggerMixin


for level in LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


class SyncLogger(logging.Logger, LoggerMixin, SyncCustomLevelMixin):

    __handlers__ = SYNC_HANDLERS

    def __init__(self, name, subname=None):
        logging.Logger.__init__(self, name)

        self.subname = subname
        self._conditional = None
        self.line_index = 0

        for handler in self.__handlers__:
            self.addHandler(handler)

        if 'LEVEL' in os.environ:
            level = LoggingLevels[os.environ['LEVEL']]
            self.setLevel(level.num)

    def _log(self, *args, **kwargs):
        if not self.conditionally_disabled:  # Reason We Override
            super(SyncLogger, self)._log(*args, **kwargs)


class AsyncLogger(aiologger.Logger, LoggerMixin, AsyncCustomLevelMixin):

    __handlers__ = ASYNC_HANDLERS

    def __init__(self, name, subname=None):
        aiologger.Logger.__init__(self, name=name)

        self.subname = subname
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
