from plumbum import colors

from .items import LogItem, LogItemLine, LogItemLines
from .formats import Format, RecordAttributes
from .utils import (
    get_record_request_method, get_record_time, get_record_status_code,
    get_record_message, get_level_formatter, get_message_formatter,
    get_record_response_reason)


def message_items(record):

    return [
        LogItem(
            formatter=RecordAttributes.METHOD,
            getter=get_record_request_method,
            suffix=":",
        ),
        LogItem(
            formatter=RecordAttributes.REASON,
            getter=get_record_response_reason,
            suffix=" -",
        ),
        LogItem(
            formatter=get_message_formatter(record),
            getter=get_record_message,
            line_index=getattr(record, 'line_index', None),
        ),
        LogItem(
            formatter=RecordAttributes.STATUS_CODE,
            getter=get_record_status_code,
        ),
    ]


def primary_items(record):
    return [
        LogItem(
            formatter=RecordAttributes.DATETIME,
            getter=get_record_time,
        ),
        LogItem(
            params="name",
            suffix=" -",
            formatter=RecordAttributes.NAME
        ),
        LogItem(
            params="levelname",
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


def proxy_lines(receord, indent=None):
    return [
        LogItem(
            params=['proxy.url'],
            formatter=RecordAttributes.PROXY,
        ),
        LogItem(
            params=['proxy.method'],
            formatter=RecordAttributes.PROXY,
        ),
        LogItem(
            params=['proxy.num_requests'],
            formatter=RecordAttributes.PROXY,
        )
    ]


def context_lines(record, indent=None):
    return [
        LogItemLine(
            LogItem(
                params='context.index',
                label="Attempt #",
                formatter=Format(colors.bold),
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                params='context.parent_index',
                label="Password #",
                formatter=Format(colors.bold),
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                params='context.password',
                label="Password",
                formatter=RecordAttributes.PASSWORD,
                indent=indent
            )
        ),
        LogItemLine(
            *proxy_lines(record),
            label="Proxy",
            indent=indent,
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
                params="other",
                indent=2,
                formatter=RecordAttributes.OTHER_MESSAGE
            ),
        ),
        *context_lines(record, indent=2),
        LogItemLine(
            LogItem(
                params="filename",
                suffix=",",
                formatter=Format(colors.fg('LightGray'))
            ),
            LogItem(
                params="lineno",
                formatter=Format(colors.bold)
            ),
            prefix="(",
            suffix=")",
            indent=2,
        )
    )
