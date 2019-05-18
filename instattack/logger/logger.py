import aiologger
import logging
import traceback
import inspect
import os

from .constants import LoggingLevels
from .handlers import SYNC_HANDLERS, ASYNC_HANDLERS


for level in LoggingLevels:
    if level.name not in logging._levelToName.keys():
        logging.addLevelName(level.num, level.name)


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

    def once(self, message, extra=None, level=LoggingLevels.DEBUG, frame_correction=0):
        """
        Logs a message one time and only one time per Python session.  This is
        useful when we want to show if we are waiting for awhile on a given
        queue retrieval, but not show that we are waiting before every retrieval
        from the queue.
        """
        if message not in self.log_once_messages:
            extra = extra or {}
            self.adjust_frame(extra, frame_correction=frame_correction + 1)

            method = getattr(self, level.name.lower())
            method(message, extra=extra)
            self.log_once_messages.append(message)

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

    def before_lines(self):
        self.line_index = 0

    def line(self, item, color='darkgray', numbered=True):
        extra = {}
        if numbered:
            extra = {'line_index': self.line_index + 1}
            self.line_index += 1
        self.bare(item, color=color, extra=extra)

    def line_by_line(self, lines, color='darkgray', numbered=True):
        self.before_lines()
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

    def _init(self, name, subname=None):
        self.subname = subname

        self._condition = None
        self.line_index = 0
        self.log_once_messages = []

        # Environment variable might not be set for usages of AppLogger
        # in __main__ module right away.
        if os.environ.get('level'):
            self.setLevel(os.environ['level'])

    def sublogger(self, subname):
        logger = self.__class__(self.name, subname=subname)
        return logger

    def conditional(self, value):
        self._condition = value

    def create_conditional(self, value, subname=None):
        logger = self.__class__(self.name, subname=subname)
        logger.conditional(value)
        return logger

    @property
    def conditionally_disabled(self):
        if self._condition is not None:
            if self._condition is False:
                return True
        return False

    def updateLevel(self):
        # Environment variable might not be set for usages of AppLogger
        # in __main__ module right away.
        if not os.environ.get('level'):
            raise RuntimeError('Level is not in the environment variables.')
        self.setLevel(os.environ['level'])

    def traceback(self, ex, raw=False):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        extra = {
            'show_stack': True,
            'frame_correction': 1,
            'stack': inspect.stack(),
        }

        ex_traceback = ex.__traceback__
        tb_lines = [
            line.rstrip('\n') for line in
            traceback.format_exception(ex.__class__, ex, ex_traceback)
        ]

        # We might have to add additional frame_correction.
        self.error("\n".join(tb_lines), extra=extra)


class SyncLogger(logging.Logger, LoggerMixin, SyncCustomLevelMixin):

    __handlers__ = SYNC_HANDLERS

    def __init__(self, name, subname=None):
        super(SyncLogger, self).__init__(name)

        self._init(name, subname=subname)
        for handler in self.__handlers__:
            self.addHandler(handler)


class AsyncLogger(aiologger.Logger, LoggerMixin, AsyncCustomLevelMixin):

    __handlers__ = ASYNC_HANDLERS

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
