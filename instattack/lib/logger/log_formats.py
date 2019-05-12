from plumbum import colors

from .items import LogItem, LogItemLine, LogItemLines
from .formats import Format, RecordAttributes, LoggingLevels
from .utils import get_level_formatter, get_message_formatter


def message_items(record):

    formatter = get_message_formatter(record)

    if getattr(record, 'is_exception', False):
        return [
            LogItem('method', formatter=RecordAttributes.METHOD),
            LogItem('msg', formatter=formatter),
            LogItem('status_code', formatter=RecordAttributes.STATUS_CODE),
        ]

    return [LogItem(
        "msg",
        formatter=formatter,
        line_index=getattr(record, 'line_index', None)
    )]


def primary_items(record):
    return [
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
            formatter=get_level_formatter(record),
        )
    ]


def simple_lines(record, indent=None):
    return [
        LogItemLine(
            *primary_items(record)
        ),
        LogItemLine(
            *message_items(record),
            indent=indent
        )
    ]


def context_lines(record, indent=None):
    return [
        LogItemLine(
            LogItem(
                'index',
                label="Attempt #",
                formatter=Format(colors.bold),
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                'parent_index',
                label="Password #",
                formatter=Format(colors.bold),
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                'password',
                label="Password",
                formatter=RecordAttributes.PASSWORD,
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                'proxy',
                label="Proxy",
                formatter=RecordAttributes.PROXY,
                indent=indent
            )
        )
    ]


def BARE_FORMAT_STRING(record):
    return LogItemLine(message_items(record))


def SIMPLE_FORMAT_STRING(record):
    return LogItemLines(
        *simple_lines(record, indent=2),
        newline=True
    )


def EXTERNAL_FORMAT_STRING(record):
    level = LoggingLevels[record.levelname]
    setattr(record, 'level', level)

    return LogItemLines(
        *simple_lines(record, indent=2),
        newline=True
    )


def LOG_FORMAT_STRING(record):

    no_indent = getattr(record, 'no_indent', False)

    return LogItemLines(
        *simple_lines(record, indent=0 if no_indent else 2),
        LogItemLine(
            LogItem(
                "other",
                indent=2,
                formatter=RecordAttributes.OTHER_MESSAGE
            ),
        ),
        *context_lines(record, indent=2),
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
            indent=2,
        )
    )
