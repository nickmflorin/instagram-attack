from artsylogger import (
    Separator, Item, Line, Lines, List, LabeledItem, LabeledLines, LabeledLine)

from .constants import RecordAttributes
from .utils import (
    get_record_request_method, get_record_time, get_record_status_code,
    get_record_message, get_level_formatter, get_message_formatter,
    get_record_response_reason)


def MESSAGE_LINE(indent=None):
    return Line(
        Item(
            value=get_record_request_method,
            formatter=RecordAttributes.METHOD,
        ),
        Separator(': '),
        Item(
            value=get_record_response_reason,
            formatter=RecordAttributes.REASON,
        ),
        Separator(' - '),
        Item(
            value=get_record_message,
            formatter=get_message_formatter,
            line_index=lambda record: getattr(record, 'line_index', None),
            line_index_formatter=RecordAttributes.LINE_INDEX,
        ),
        Item(
            value=get_record_status_code,
            formatter=RecordAttributes.STATUS_CODE,
        ),
        indent=indent,
    )


PRIMARY_LINE = Line(
    Item(
        formatter=RecordAttributes.DATETIME,
        value=get_record_time,
    ),
    Item(
        value="name",
        formatter=RecordAttributes.NAME
    ),
    Separator(': '),
    Item(
        value="subname",
        formatter=RecordAttributes.SUBNAME
    ),
    Separator('  '),
    Item(
        value=["level.name"],
        formatter=get_level_formatter,
    )
)


CONTEXT_LINES = Lines(
    LabeledLines(
        LabeledItem(
            value=['index', 'context.index'],
            label="Index",
        ),
        LabeledItem(
            value=['parent_index', 'context.parent_index'],
            label="Parent Index",
        ),
        LabeledItem(
            value=['password', 'context.password'],
            label="Password",
            formatter=RecordAttributes.PASSWORD,  # Override
        ),
        label_formatter=RecordAttributes.LABEL,
        formatter=RecordAttributes.CONTEXT_ATTRIBUTE,
        indent=2
    ),
    Lines(
        LabeledLine(
            Item(
                value=['proxy.method', 'context.proxy.method'],
                formatter=RecordAttributes.METHOD,
            ),
            Item(
                value=['proxy.url', 'context.proxy.url'],
                formatter=RecordAttributes.PROXY
            ),
            label="Proxy",
            indent=2,
            label_formatter=RecordAttributes.LABEL,
        ),
        # Also formatter to be passed into group and be used for every item
        # in the group, but can be overridden for individual items
        # EXTERNALIZE PACKAGE AS ARTSY LOGGER
        LabeledLines(
            LabeledItem(
                value=['proxy.humanized_state', 'context.proxy.humanized_state'],
                label="State",
            ),
            LabeledItem(
                value=["proxy.flattened_error_rate", "context.proxy.flattened_error_rate"],
                label="Error Rate (Flat)",
            ),
            LabeledItem(
                value=["proxy.avg_res_time", "context.proxy.avg_res_time"],
                label="Avg. Resp Time",
            ),
            LabeledItem(
                value=["proxy.num_active_requests", "context.proxy.num_active_requests"],
                label="Num Requests",
            ),
            label_formatter=RecordAttributes.LABEL,
        ),
        indent=2 + 2,
        formatter=RecordAttributes.CONTEXT_ATTRIBUTE,
        lines_above=0,
        lines_below=1,
    )
)


TRACEBACK_LINE = Line(
    Separator('('),
    Item(
        value="pathname",
        formatter=RecordAttributes.PATHNAME
    ),
    Separator(', '),
    Item(
        value="funcName",
        formatter=RecordAttributes.FUNCNAME
    ),
    Separator(', '),
    Item(
        value="lineno",
        formatter=RecordAttributes.LINENO
    ),
    Separator(')'),
    indent=2,
)


BARE_FORMAT_STRING = MESSAGE_LINE(indent=None)


SIMPLE_FORMAT_STRING = Lines(
    PRIMARY_LINE,
    MESSAGE_LINE(indent=2)
)


LOG_FORMAT_STRING = Lines(
    PRIMARY_LINE,
    MESSAGE_LINE(indent=2),
    Line(
        Item(
            value="other",
            indent=2,
            formatter=RecordAttributes.OTHER_MESSAGE
        ),
    ),
    List(
        value="list",
        indent=2,
        formatter=RecordAttributes.OTHER_MESSAGE,
        line_index_formatter=RecordAttributes.LINE_INDEX,
        lines_above=0,
        lines_below=0
    ),
    CONTEXT_LINES,
    TRACEBACK_LINE,
    lines_above=1,
    lines_below=0,
    header_char="-",
)
