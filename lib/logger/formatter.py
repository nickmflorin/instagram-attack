from datetime import datetime
from plumbum import colors

from lib.http import get_exception_request_method, get_exception_status_code
from lib.err_handling import get_exception_message

from .formats import RecordAttributes, Format, LoggingLevels, DATE_FORMAT
from .items import LogItemSet, LogItemLine, LogLabeledItem, LogItem
from .utils import optional_indent, flexible_retrieval


def EXCEPTION_FORMAT_STRING(record, indent=None):
    return LogItemLine(
        LogItem('method', formatter=RecordAttributes.METHOD),
        LogItem('message', formatter=record.extra['level']),
        LogItem('status_code', formatter=RecordAttributes.STATUS_CODE),
        indent=indent
    )


def MESSAGE_FORMAT_STRING(record):

    if record.extra['is_exception']:
        return EXCEPTION_FORMAT_STRING(record)

    # Default
    formatter = Format(record.extra['level'].format.colors[0])

    if record.extra.get('highlight'):
        formatter = RecordAttributes.SPECIAL_MESSAGE

    elif record.extra.get('color'):
        color = record.extra['color']
        if isinstance(color, str):
            color = colors.fg(color)
        formatter = Format(color)

    return LogItem("message", formatter=formatter)


def BARE_FORMAT_STRING(record):
    return LogItemLine(MESSAGE_FORMAT_STRING(record))


def SIMPLE_FORMAT_STRING(record):
    return LogItemSet(
        LogItemLine(
            LogItem('datetime', formatter=RecordAttributes.DATETIME),
            MESSAGE_FORMAT_STRING(record)
        )
    )


def LOG_FORMAT_STRING(record):

    no_indent = record.extra.get('no_indent', False),
    opt_indent = optional_indent(no_indent=no_indent)

    return (
        LogItemSet(
            LogItemLine(
                LogItem('datetime', formatter=RecordAttributes.DATETIME),
                LogItem("channel", suffix=" -", formatter=RecordAttributes.CHANNEL),
                LogItem("level_name", suffix=" ", formatter=record.extra['level'].format),
                MESSAGE_FORMAT_STRING(record),
            ),
            LogItem("other_message", indent=opt_indent(4), formatter=RecordAttributes.MESSAGE),

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


def record_formatter(format_string=LOG_FORMAT_STRING):

    def _record_formatter(record, handler):

        format_context = {}

        level = LoggingLevels[record.level_name]
        record.extra['level'] = level

        format_context['datetime'] = datetime.now().strftime(DATE_FORMAT)
        format_context['channel'] = record.channel
        format_context['level_name'] = record.level_name

        level.format(record.level_name)
        format_context['message'] = record.message

        record.extra['is_exception'] = False
        if isinstance(record.message, Exception):
            record.extra['is_exception'] = True

            format_context['status_code'] = get_exception_status_code(record.message)
            format_context['message'] = get_exception_message(record.message)
            format_context['method'] = get_exception_request_method(record.message)

        # TODO: Might want to format 'other' message differently.
        format_context['other_message'] = flexible_retrieval(record, 'other')
        format_context['index'] = flexible_retrieval(record, 'index')
        format_context['parent_index'] = flexible_retrieval(record, 'parent_index')
        format_context['password'] = flexible_retrieval(record, 'password')

        format_context['proxy'] = flexible_retrieval(record, 'proxy', tier_key='host')

        # Allow traceback to be overridden.
        format_context['lineno'] = flexible_retrieval(record, 'lineno')
        format_context['filename'] = flexible_retrieval(record, 'filename')

        return format_string(record).format(**format_context)

    return _record_formatter
