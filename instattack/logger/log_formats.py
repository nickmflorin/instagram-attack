from instattack.artsylogger import (
    Separator, Item, Line, Lines, List, LabeledItem, LabeledLines, LabeledLine)

from .constants import RecordAttributes
from .utils import (
    get_record_request_method, get_record_time, get_record_status_code,
    get_record_message, get_level_formatter, get_message_formatter,
    get_record_response_reason)


def message_line(record):
    return Line(
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
            line_index_formatter=RecordAttributes.LINE_INDEX,
        ),
        Item(
            formatter=RecordAttributes.STATUS_CODE,
            getter=get_record_status_code,
        ),
    )


def primary_line(record):
    return Line(
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
    )


def context_lines(record, indent=None):
    return Lines(
        LabeledLines(
            LabeledItem(
                params=['index', 'context.index'],
                label="Index",
            ),
            LabeledItem(
                params=['parent_index', 'context.parent_index'],
                label="Parent Index",
            ),
            LabeledItem(
                params=['password', 'context.password'],
                label="Password",
                formatter=RecordAttributes.PASSWORD,  # Override
            ),
            label_formatter=RecordAttributes.LABEL,
            formatter=RecordAttributes.CONTEXT_ATTRIBUTE,
            indent=indent
        ),
        Lines(
            LabeledLine(
                Item(
                    params=['proxy.method', 'context.proxy.method'],
                    formatter=RecordAttributes.METHOD,
                ),
                Item(
                    params=['proxy.url', 'context.proxy.url'],
                    formatter=RecordAttributes.PROXY
                ),
                label="Proxy",
                indent=indent,
                label_formatter=RecordAttributes.LABEL,
            ),
            # Also formatter to be passed into group and be used for every item
            # in the group, but can be overridden for individual items
            # EXTERNALIZE PACKAGE AS ARTSY LOGGER
            LabeledLines(
                LabeledItem(
                    params=['proxy.humanized_state', 'context.proxy.humanized_state'],
                    label="State",
                ),
                LabeledItem(
                    params=["proxy.flattened_error_rate", "context.proxy.flattened_error_rate"],
                    label="Error Rate (Flat)",
                ),
                LabeledItem(
                    params=["proxy.avg_res_time", "context.proxy.avg_res_time"],
                    label="Avg. Resp Time",
                ),
                LabeledItem(
                    params=["proxy.num_active_requests", "context.proxy.num_active_requests"],
                    label="Num Requests",
                ),
                label_formatter=RecordAttributes.LABEL,
            ),
            indent=(indent + 2 if indent else None),
            formatter=RecordAttributes.CONTEXT_ATTRIBUTE,
            lines_above=0,
            lines_below=1,
        )
    )


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
    return message_line(record)


def SIMPLE_FORMAT_STRING(record):
    return Lines(
        primary_line(record),
        message_line(record, indent=2),
    )


def LOG_FORMAT_STRING(record):
    return Lines(
        Lines(
            primary_line(record),
            message_line(record, indent=2),
        ),
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
        context_lines(record, indent=2),
        traceback_line(record, indent=2),
        lines_above=1,
        lines_below=0,
        header_char="-",
    )
