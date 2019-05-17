import logging

import inspect
from plumbum import colors
import traceback
import os
import sys

from .formats import LoggingLevels
from .setup import add_base_handlers


log = logging.getLogger('AppLogger')


def log_conditionally(func):
    def wrapped(instance, *args, **kwargs):
        if instance._condition is not None:
            if instance._condition:
                return
            func(instance, *args, **kwargs)
        else:
            func(instance, *args, **kwargs)
    return wrapped


class AppLogger(logging.Logger):

    def __init__(self, *args, **kwargs):
        self.subname = kwargs.pop('subname', None)
        super(AppLogger, self).__init__(*args, **kwargs)

        self.line_index = 0
        self.log_once_messages = []

        add_base_handlers(self)
        self._condition = None

        # Environment variable might not be set for usages of AppLogger
        # in __main__ module right away.
        if os.environ.get('level'):
            self.setLevel(os.environ['level'])

    def sublogger(self, subname):
        logger = self.__class__(self.name, subname=subname)
        return logger

    def conditional(self, value):
        self._condition = value

    def updateLevel(self):
        # Environment variable might not be set for usages of AppLogger
        # in __main__ module right away.
        if not os.environ.get('level'):
            raise RuntimeError('Level is not in the environment variables.')
        self.setLevel(os.environ['level'])

    def default(self, record, attr, default=None):
        setattr(record, attr, getattr(record, attr, default))

    def makeRecord(self, *args, **kwargs):
        record = super(AppLogger, self).makeRecord(*args, **kwargs)
        setattr(record, 'subname', self.subname)

        self.default(record, 'level_format')
        self.default(record, 'line_index')
        self.default(record, 'show_level', default=True)
        self.default(record, 'highlight', default=False)
        self.default(record, 'color')

        if getattr(record, 'level', None) is None:
            setattr(record, 'level', LoggingLevels[record.levelname])

        if not record.show_level:
            record.levelname = None

        self.default(record, 'is_exception', default=False)
        if isinstance(record.msg, Exception):
            record.is_exception = True

        if record.color:
            if isinstance(record.color, str):
                setattr(record, 'color', colors.fg(record.color))

        if getattr(record, 'frame_correction', None):
            for key, val in record.frame_correction.items():
                setattr(record, key, val)

        return record

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

    def adjust_frame(self, extra, frame_correction=1):
        from instattack.lib import traceback_to
        tb_context = traceback_to(inspect.stack(), frame_correction=frame_correction + 1)
        extra.update(frame_correction=tb_context)

    # @log_conditionally
    # def info(self, message, extra=None, frame_correction=0):

    #     extra = extra or {}
    #     self.adjust_frame(extra, frame_correction=frame_correction + 1)
    #     if 'level' not in extra:
    #         extra.update(level=LoggingLevels.INFO)

    #     super(AppLogger, self).info(message, extra=extra)

    def success(self, message, extra=None, frame_correction=0):
        extra = extra or {}
        extra.update(level=LoggingLevels.SUCCESS, show_level=False)

        self.adjust_frame(extra, frame_correction=frame_correction + 1)
        self.info(message, extra=extra)

    @log_conditionally
    def start(self, message, extra=None, frame_correction=0):
        extra = extra or {}
        extra.update(level=LoggingLevels.START, show_level=False)

        self.adjust_frame(extra, frame_correction=frame_correction + 1)
        self.info(message, extra=extra)

    def stop(self, message, extra=None, frame_correction=0):
        extra = extra or {}
        extra.update(level=LoggingLevels.STOP, show_level=False)

        self.adjust_frame(extra, frame_correction=frame_correction + 1)
        self.info(message, extra=extra)

    @log_conditionally
    def complete(self, message, extra=None, frame_correction=0):
        extra = extra or {}
        extra.update(level=LoggingLevels.COMPLETE, show_level=False)

        self.adjust_frame(extra, frame_correction=frame_correction + 1)
        self.info(message, extra=extra)

    def simple(self, message, color=None, extra=None, frame_correction=0):

        default = {'color': color, 'simple': True}
        extra = extra or {}
        default.update(**extra)

        self.adjust_frame(extra, frame_correction=frame_correction + 1)
        self.info(message, extra=default)

    def bare(self, message, color='darkgray', extra=None, frame_correction=0):

        default = {'color': color, 'bare': True}
        extra = extra or {}
        default.update(**extra)

        self.adjust_frame(extra, frame_correction=frame_correction + 1)
        self.info(message, extra=default)

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

    # We might now need this anymore?
    def traceback(self, ex, raw=False):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        from instattack.lib import traceback_to
        extra = {'no_indent': True}

        ex_traceback = ex.__traceback__
        tb_lines = [
            line.rstrip('\n') for line in
            traceback.format_exception(ex.__class__, ex, ex_traceback)
        ]

        tb_context = traceback_to(inspect.stack(), back=1)
        extra.update(frame_correction=tb_context)

        # This can be used if we want to just output the raw error.
        if raw:
            for line in tb_lines:
                sys.stderr.write("%s\n" % line)
        else:
            self.error("\n".join(tb_lines), extra=extra)
