from .items import Separator, Item, Line, Lines, List
from .constants import RecordAttributes
from .utils import (
    get_record_request_method, get_record_time, get_record_status_code,
    get_record_message, get_level_formatter, get_message_formatter,
    get_record_response_reason)


def message_items(record):
    return [
        Item(
            formatter=RecordAttributes.METHOD,
            getter=get_record_request_method,
        ),
        Separator(': '),
        Item(
            formatter=RecordAttributes.REASON,
            getter=get_record_response_reason,
        ),
        Separator(' - '),
        Item(
            formatter=get_message_formatter(record),
            getter=get_record_message,
            line_index=getattr(record, 'line_index', None),
        ),
        Item(
            formatter=RecordAttributes.STATUS_CODE,
            getter=get_record_status_code,
        ),
    ]


def primary_items(record):
    return [
        Item(
            formatter=RecordAttributes.DATETIME,
            getter=get_record_time,
        ),
        Item(
            params="name",
            formatter=RecordAttributes.NAME
        ),
        Separator(': '),
        Item(
            params="subname",
            formatter=RecordAttributes.SUBNAME
        ),
        Separator('  '),
        Item(
            params=["level.name"],
            formatter=get_level_formatter(record),
        )
    ]


def simple_lines(record, indent=None):
    return [
        Line(
            *primary_items(record)
        ),
        Line(
            *message_items(record),
            indent=indent
        )
    ]


def proxy_lines(record, indent=None):
    return [
        Item(
            params=['proxy.method', 'context.proxy.method'],
            formatter=RecordAttributes.METHOD,
        ),
        Item(
            params=['proxy.url', 'context.proxy.url'],
            formatter=RecordAttributes.PROXY
        ),
        Item(
            params=['proxy.humanized_state', 'context.proxy.humanized_state'],
            formatter=RecordAttributes.PROXY_STATE,
        ),
        Item(
            label="Num Requests",
            params=['proxy.num_requests', 'context.proxy.num_requests'],
            formatter=RecordAttributes.NUM_REQUESTS,
        )
    ]


def context_lines(record, indent=None):
    return [
        Line(
            Item(
                params=['index', 'context.index'],
                label="Index",
                formatter=RecordAttributes.INDEX,
                indent=indent
            )
        ),
        Line(
            Item(
                params=['parent_index', 'context.parent_index'],
                label="Parent Index",
                formatter=RecordAttributes.INDEX,
                indent=indent
            )
        ),
        Line(
            Item(
                params=['password' 'context.password'],
                label="Password",
                formatter=RecordAttributes.PASSWORD,
                indent=indent
            )
        ),
        Line(
            *proxy_lines(record),
            label="Proxy",
            indent=indent,
        )
    ]


def traceback_line(record, indent=None):
    return Line(
        Separator('('),
        Item(
            params="pathname",
            formatter=RecordAttributes.PATHNAME
        ),
        Separator(', '),
        Item(
            params="funcName",
            formatter=RecordAttributes.FUNCNAME
        ),
        Separator(', '),
        Item(
            params="lineno",
            formatter=RecordAttributes.LINENO
        ),
        Separator(')'),
        indent=indent,
    )


def BARE_FORMAT_STRING(record):
    return Line(*message_items(record))


def SIMPLE_FORMAT_STRING(record):
    return Lines(
        *simple_lines(record, indent=2),
        lines_above=1
    )


def TRACEBACK_FORMAT_STRING(record):
    return Lines(
        Line(*primary_items(record)),
        Line(Item(
            params=['msg'],
            formatter=get_message_formatter(record),
        ))
    )


def LOG_FORMAT_STRING(record):
    return Lines(
        *simple_lines(record, indent=2),
        Line(
            Item(
                params="other",
                indent=2,
                formatter=RecordAttributes.OTHER_MESSAGE
            ),
        ),
        List(
            params="list",
            indent=2,
            formatter=RecordAttributes.OTHER_MESSAGE,
            line_index_formatter=RecordAttributes.LINE_INDEX,
            lines_above=0,
            lines_below=0
        ),
        Lines(
            *context_lines(record, indent=2),
            lines_above=1,
            lines_below=1,
        ),
        Lines(
            traceback_line(record, indent=2),
            lines_above=0,
            lines_below=0
        ),
        lines_above=1,
        lines_below=0,
        header_char="-",
    )
