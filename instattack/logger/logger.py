import aiologger
import logging

from .constants import LoggingLevels
from .handlers import SYNC_HANDLERS, ASYNC_HANDLERS
from .mixins import SyncCustomLevelMixin, AsyncCustomLevelMixin, LoggerMixin


for level in LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


class AdaptableLogger(object):

    def adapt(self, obj):
        """
        Returns a copy of this instantiated logger class with the log methods
        adapted to a new object.  Useful for adjusting the logging methods in
        a single object and passing in the object.

        Usage
        -----

        >>> class Adapter(object):
        >>>     def info(self, message):
        >>>         print(f"Adapted Message {message}")
        >>>
        >>> log = logger.get_sync('Test Logger')
        >>> new_log = log.adapt(Adapter)
        >>> new_log.info('Test')
        >>>
        >>> "Adapted Message Test"
        """
        adapted_logger = type(
            'adapted_logger', self.__class__.__bases__, dict(self.__class__.__dict__))

        methods = [
            method_name for method_name in dir(obj)
            if (
                callable(getattr(obj, method_name)) and method_name in self.adaptable
            )
        ]

        for method_name in methods:
            new_method = getattr(obj, method_name)
            # Produces a callable that behaves like the new method, but
            # automatically passes in `self` as the first argument.
            new_method = new_method.__get__(self)
            setattr(adapted_logger, method_name, new_method)

        return adapted_logger


class SyncLogger(logging.Logger, LoggerMixin, SyncCustomLevelMixin, AdaptableLogger):

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


class AsyncLogger(aiologger.Logger, LoggerMixin, AsyncCustomLevelMixin, AdaptableLogger):

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
