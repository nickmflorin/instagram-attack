import contextlib
import logbook
import progressbar
from plumbum import colors
import traceback
import sys

from .formats import Format, LoggingLevels, RecordAttributes
from .logging import (format_log_message,
    LogItemSet, LogItemLine, LogLabeledItem, LogItem)


__all__ = ('AppLogger', 'log_handling', )


DATE_FORMAT_OBJ = Format(colors.yellow)
DATE_FORMAT = DATE_FORMAT_OBJ('%Y-%m-%d %H:%M:%S')


def LOG_FORMAT_STRING(no_indent=False):

    def opt_indent(val):
        if not no_indent:
            return val
        return 0

    return (
        LogItemSet(
            LogItemLine(
                LogItem("channel", suffix=":", formatter=RecordAttributes.CHANNEL),
                LogItem("formatted_level_name"),
            ),
            LogItem("formatted_message", indent=opt_indent(4)),
            LogItem("other_message", indent=opt_indent(4),
                formatter=RecordAttributes.MESSAGE),

            LogLabeledItem('index', label="Attempt #",
                formatter=Format(colors.bold), indent=opt_indent(6)),
            LogLabeledItem('parent_index', label="Password #",
                formatter=Format(colors.bold), indent=opt_indent(6)),
            LogLabeledItem('password', label="Password",
                formatter=RecordAttributes.PASSWORD, indent=opt_indent(6)),
            LogLabeledItem('proxy', label="Proxy",
                formatter=RecordAttributes.PROXY, indent=opt_indent(6)),

            LogItemLine(
                LogItem("filename", suffix=",", formatter=Format(colors.fg('LightGray'))),
                LogItem("lineno", formatter=Format(colors.bold)),
                prefix="(",
                suffix=")",
                indent=opt_indent(4),
            )
        )
    )


def app_formatter(record, handler):

    def flexible_retrieval(param, tier_key=None):
        """
        Priorities overridden values explicitly provided in extra, and will
        check record.extra['context'] if the value is not in 'extra'.

        If tier_key is provided and item found is object based, it will try
        to use the tier_key to get a non-object based value.
        """
        def flexible_obj_get(value):
            if hasattr(value, '__dict__') and tier_key:
                return getattr(value, tier_key)
            return value

        if record.extra.get(param):
            return flexible_obj_get(record.extra[param])
        else:
            if hasattr(record, param):
                return getattr(record, param)
            else:
                if record.extra.get('context'):
                    ctx = record.extra['context']
                    if hasattr(ctx, param):
                        value = getattr(ctx, param)
                        return flexible_obj_get(value)
            return None

    format_context = {}

    level = LoggingLevels[record.level_name]
    format_context['channel'] = record.channel
    format_context['formatted_level_name'] = level.format(record.level_name)
    format_context['formatted_message'] = format_log_message(
        record.message, level, extra=record.extra)

    # TODO: Might want to format 'other' message differently.
    format_context['other_message'] = flexible_retrieval('other')

    format_context['index'] = flexible_retrieval('index')
    format_context['parent_index'] = flexible_retrieval('parent_index')
    format_context['password'] = flexible_retrieval('password')

    format_context['proxy'] = flexible_retrieval('proxy', tier_key='host')

    # Allow traceback to be overridden.
    format_context['lineno'] = flexible_retrieval('lineno')
    format_context['filename'] = flexible_retrieval('filename')

    return LOG_FORMAT_STRING(
        no_indent=record.extra.get('no_indent', False),
    ).format(**format_context)


def _stream_handler(level='INFO', format_string=None, filter=None):
    handler = logbook.StreamHandler(
        sys.stdout,
        level=level,
        filter=filter,
        bubble=True
    )
    handler.format_string = format_string
    return handler


def base_handler(level=None):
    """
    We want to lazy evaluate the initialization of StreamHandler for purposes
    of progressbar implementation with logging.
    """
    handler = _stream_handler(level=level)
    handler.formatter = app_formatter
    return handler


class log_handling(object):

    def __init__(self, level):
        self.level = level

    def __call__(self, f):

        def wrapped(instance, *args, **kwargs):
            if self.level == 'self':
                self.level = getattr(instance, 'level')

            with self.context():
                return f(instance, *args, **kwargs)
        return wrapped

    @contextlib.contextmanager
    def context(self):
        self._init_progressbar()
        try:
            with base_handler(level=self.level):
                yield
        finally:
            self._deinit_progressbar()

    def _init_progressbar(self):
        progressbar.streams.wrap_stderr()
        progressbar.streams.wrap_stdout()

    def _deinit_progressbar(self):
        progressbar.streams.unwrap_stdout()
        progressbar.streams.unwrap_stderr()


class AppLogger(logbook.Logger):

    def traceback(self, ex, ex_traceback=None, raw=False):
        """
        We are having problems with logbook and asyncio in terms of logging
        exceptions with their traceback.  For now, this is a workaround that
        works similiarly.
        """
        if ex_traceback is None:
            ex_traceback = ex.__traceback__

        tb_lines = [
            line.rstrip('\n') for line in
            traceback.format_exception(ex.__class__, ex, ex_traceback)
        ]

        # This can be used if we want to just output the raw error.
        if raw:
            for line in tb_lines:
                sys.stderr.write("%s\n" % line)
        else:
            self.error("\n".join(tb_lines), extra={'no_indent': True})
