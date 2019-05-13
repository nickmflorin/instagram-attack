import logging

import inspect
from plumbum import colors
import traceback
import os
import sys

from .formats import LoggingLevels
from .setup import add_base_handlers


class AppLogger(logging.Logger):

    def __init__(self, *args, **kwargs):
        super(AppLogger, self).__init__(*args, **kwargs)
        self.line_index = 0
        add_base_handlers(self)

        # Environment variable might not be set for usages of AppLogger
        # in __main__ module right away.
        if os.environ.get('level'):
            self.setLevel(os.environ['level'])

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

    def note(self, message, extra=None):
        from instattack.lib import traceback_to

        extra = extra or {}
        extra.update(level=LoggingLevels.NOTE, show_level=False)

        tb_context = traceback_to(inspect.stack(), back=1)
        extra.update(frame_correction=tb_context)

        self.info(message, extra=extra)

    def start(self, message, extra=None):
        from instattack.lib import traceback_to

        extra = extra or {}
        extra.update(level=LoggingLevels.START, show_level=False)

        tb_context = traceback_to(inspect.stack(), back=1)
        extra.update(frame_correction=tb_context)

        self.info(message, extra=extra)

    def stop(self, message, extra=None):
        from instattack.lib import traceback_to

        extra = extra or {}
        extra.update(level=LoggingLevels.STOP, show_level=False)

        tb_context = traceback_to(inspect.stack(), back=1)
        extra.update(frame_correction=tb_context)

        self.info(message, extra=extra)

    def complete(self, message, extra=None):
        from instattack.lib import traceback_to

        extra = extra or {}
        extra.update(level=LoggingLevels.COMPLETE, show_level=False)

        tb_context = traceback_to(inspect.stack(), back=1)
        extra.update(frame_correction=tb_context)

        self.info(message, extra=extra)

    def simple(self, message, color=None, extra=None):
        from instattack.lib import traceback_to

        default = {'color': color, 'simple': True}
        extra = extra or {}
        default.update(**extra)

        tb_context = traceback_to(inspect.stack(), back=1)
        default.update(frame_correction=tb_context)

        self.info(message, extra=default)

    def bare(self, message, color='darkgray', extra=None):
        from instattack.lib import traceback_to

        default = {'color': color, 'bare': True}
        extra = extra or {}
        default.update(**extra)

        tb_context = traceback_to(inspect.stack(), back=1)
        default.update(frame_correction=tb_context)

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
