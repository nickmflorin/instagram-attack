import aiologger
import logging

from .constants import LoggingLevels
from .handlers import SYNC_HANDLERS, ASYNC_HANDLERS
from .mixins import SyncCustomLevelMixin, AsyncCustomLevelMixin, LoggerMixin


for level in LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


class SyncLogger(logging.Logger, LoggerMixin, SyncCustomLevelMixin):

    __handlers__ = SYNC_HANDLERS
    adaptable = ('info', 'warning', 'debug', 'error', 'critical', )

    def __init__(self, name, subname=None):
        super(SyncLogger, self).__init__(name)

        self._init(name, subname=subname)
        for handler in self.__handlers__:
            self.addHandler(handler)

    def _log(self, *args, **kwargs):
        if not self.conditionally_disabled:  # Reason We Override
            super(SyncLogger, self)._log(*args, **kwargs)


class AsyncLogger(aiologger.Logger, LoggerMixin, AsyncCustomLevelMixin):

    __handlers__ = ASYNC_HANDLERS
    adaptable = ('info', 'warning', 'debug', 'error', 'critical', )

    def __init__(self, name, subname=None):
        aiologger.Logger.__init__(self, name=name)

        self._init(name, subname=subname)
        for handler in self.__handlers__:
            self.addHandler(handler)

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
            setattr(record, 'subname', self.subname)  # Reason We Override
            await self.handle(record)
