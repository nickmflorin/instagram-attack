from .items import LogItem, LogItemLine, LogItemLines
from .formats import RecordAttributes, LoggingLevels
from .utils import (
    get_record_request_method, get_record_time, get_record_status_code,
    get_record_message, get_level_formatter, get_message_formatter,
    get_record_response_reason)


def message_items(record):

    return [
        LogItem(
            formatter=record.level.formats.get(
                'method', RecordAttributes.METHOD),
            getter=get_record_request_method,
            suffix=":",
        ),
        LogItem(
            formatter=record.level.formats.get(
                'reason', RecordAttributes.REASON),
            getter=get_record_response_reason,
            suffix=" -",
        ),
        LogItem(
            formatter=get_message_formatter(record),
            getter=get_record_message,
            line_index=getattr(record, 'line_index', None),
        ),
        LogItem(
            formatter=record.level.formats.get(
                'status_code', RecordAttributes.STATUS_CODE),
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
            formatter=record.level.formats.get(
                'name', RecordAttributes.NAME),
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


def proxy_lines(record, indent=None):
    return [
        LogItem(
            params=['proxy.method', 'context.proxy.method'],
            formatter=record.level.formats.get(
                'method', RecordAttributes.METHOD),
        ),
        LogItem(
            params=['proxy.url', 'context.proxy.url'],
            formatter=record.level.formats.get(
                'proxy', RecordAttributes.PROXY),
        ),
        LogItem(
            label="Num Requests",
            params=['proxy.num_requests', 'context.proxy.num_requests'],
            formatter=record.level.formats.get(
                'num_requests', RecordAttributes.NUM_REQUESTS),
        )
    ]


def context_lines(record, indent=None):
    return [
        LogItemLine(
            LogItem(
                params=['index', 'context.index'],
                label="Index",
                formatter=record.level.formats.get(
                    'index', RecordAttributes.INDEX),
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                params=['parent_index', 'context.parent_index'],
                label="Parent Index",
                formatter=record.level.formats.get(
                    'index', RecordAttributes.INDEX),
                indent=indent
            )
        ),
        LogItemLine(
            LogItem(
                params=['password' 'context.password'],
                label="Password",
                formatter=record.level.formats.get(
                    'password', RecordAttributes.PASSWORD),
                indent=indent
            )
        ),
        LogItemLine(
            *proxy_lines(record),
            label="Proxy",
            indent=indent,
        )
    ]


def traceback_line(record, indent=None):
    return LogItemLine(
        LogItem(
            params="filename",
            suffix=",",
            formatter=record.level.formats.get(
                'filename', RecordAttributes.FILENAME)
        ),
        LogItem(
            params="funcName",
            suffix=",",
            formatter=record.level.formats.get(
                'funcName', RecordAttributes.FUNCNAME)
        ),
        LogItem(
            params="lineno",
            formatter=record.level.formats.get(
                'lineno', RecordAttributes.LINENO)
        ),
        prefix="(",
        suffix=")",
        indent=indent,
    )


def BARE_FORMAT_STRING(record):
    return LogItemLine(*message_items(record))


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
                formatter=record.level.formats.get(
                    'other', RecordAttributes.OTHER_MESSAGE)
            ),
        ),
        *context_lines(record, indent=2),
        traceback_line(record, indent=2),
    )
