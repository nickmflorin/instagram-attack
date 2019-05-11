from enum import Enum
from plumbum import colors

from .items import LogItem, LogItemLine, LogItemLines
from .utils import optional_indent


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class Format(object):
    def __init__(self, *args, wrapper=None):
        self.colors = args
        self.wrapper = wrapper

    def __call__(self, text):
        # TODO: Figure out how to dynamically create color tuples.
        if self.wrapper:
            text = self.wrapper % text

        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        return (c | text)


class FormattedEnum(Enum):

    def __init__(self, format):
        self.format = format

    def __call__(self, text):
        return self.format(text)


class LoggingLevels(FormattedEnum):

    CRITICAL = Format(colors.fg('Magenta'), colors.bold)
    ERROR = Format(colors.fg('Red'), colors.underline)
    WARNING = Format(colors.fg('Gold3A'))
    NOTICE = Format(colors.fg('Green4'))
    INFO = Format(colors.fg('DeepSkyBlue2'))
    DEBUG = Format(colors.fg('DarkGray'))


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Format(colors.black, wrapper="[%s] ")
    DATETIME = Format(colors.fg('LightYellow3'))
    LABEL = Format(colors.black, colors.underline, wrapper="%s: ")
    MESSAGE = Format(colors.black)
    SPECIAL_MESSAGE = Format(colors.bg('LightGray'), colors.fg('Magenta'))
    NAME = Format(colors.fg('Grey3'))
    PROXY = Format(colors.fg('CadetBlueA'), wrapper="<%s>")
    TOKEN = Format(colors.red)
    STATUS_CODE = Format(colors.red, wrapper="[%s]")
    METHOD = Format(colors.black, colors.bold)
    TASK = Format(colors.fg('LightBlue'), wrapper="(%s)")
    PASSWORD = Format(colors.black, colors.bold)


def EXCEPTION_FORMAT_STRING(format_context, indent=None):
    return LogItemLine(
        LogItem('method', formatter=RecordAttributes.METHOD),
        LogItem('message', formatter=format_context['level']),
        LogItem('status_code', formatter=RecordAttributes.STATUS_CODE),
        indent=indent
    )


def MESSAGE_FORMAT_STRING(record):

    if record.is_exception:
        return EXCEPTION_FORMAT_STRING(record)

    if record.highlight:
        formatter = RecordAttributes.SPECIAL_MESSAGE
    elif record.color:
        formatter = Format(record.color)
    else:
        formatter = Format(record.level.format.colors[0])

    return LogItem("message", formatter=formatter, line_index=record.line_index)


def BARE_FORMAT_STRING(record):
    return MESSAGE_FORMAT_STRING(record)


def SIMPLE_FORMAT_STRING(record):
    return LogItemLine(
        LogItem('datetime', formatter=RecordAttributes.DATETIME),
        MESSAGE_FORMAT_STRING(record)
    )


def LOG_FORMAT_STRING(record):

    # no_indent = record.extra.get('no_indent', False),
    opt_indent = optional_indent(no_indent=False)

    return LogItemLines(
        LogItemLine(
            LogItem(
                'datetime',
                formatter=RecordAttributes.DATETIME
            ),
            LogItem(
                "name",
                suffix=" -",
                formatter=RecordAttributes.NAME
            ),
            LogItem(
                "levelname",
                suffix=" ",
                formatter=record.level.format
            ),
            MESSAGE_FORMAT_STRING(record)
        ),
        LogItem(
            "other",
            indent=opt_indent(4),
            formatter=RecordAttributes.MESSAGE
        ),
        LogItem(
            'index',
            label="Attempt #",
            formatter=Format(colors.bold),
            indent=opt_indent(6)
        ),
        LogItem(
            'parent_index',
            label="Password #",
            formatter=Format(colors.bold),
            indent=opt_indent(6)
        ),
        LogItem(
            'password',
            label="Password",
            formatter=RecordAttributes.PASSWORD,
            indent=opt_indent(6)
        ),
        LogItem(
            'proxy',
            label="Proxy",
            formatter=RecordAttributes.PROXY,
            indent=opt_indent(6)
        ),
        LogItemLine(
            LogItem(
                "filename",
                suffix=",",
                formatter=Format(colors.fg('LightGray'))
            ),
            LogItem(
                "lineno",
                formatter=Format(colors.bold)
            ),
            prefix="(",
            suffix=")",
            indent=opt_indent(4),
        )
    )
