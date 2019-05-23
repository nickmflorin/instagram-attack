import logging
from artsylogger import (
    Item, Line, Lines, Header, Label, LineIndex)

from .constants import RecordAttributes
from .utils import (
    get_record_request_method, get_record_time, get_record_status_code,
    get_record_message, get_level_formatter, get_message_formatter,
    get_record_response_reason)


SIMPLE_FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINE = Line(
    Item(
        value=get_record_request_method,
        formatter=RecordAttributes.METHOD,
        suffix=": "
    ),
    Item(
        value=get_record_response_reason,
        formatter=RecordAttributes.REASON,
        suffix=" - ",
    ),
    Item(
        value=get_record_message,
        formatter=get_message_formatter,
        line_index=LineIndex(
            value=lambda record: getattr(record, 'line_index', None),
            formatter=RecordAttributes.LINE_INDEX
        )
    ),
    Item(
        value=get_record_status_code,
        formatter=RecordAttributes.STATUS_CODE,
        wrapper="[%s]"
    ),
)


PRIMARY_LINE = Line(
    Item(
        formatter=RecordAttributes.DATETIME,
        value=get_record_time,
        wrapper="[%s]"
    ),
    Item(
        value="name",
        formatter=RecordAttributes.NAME,
        suffix=": "
    ),
    Item(
        value="subname",
        formatter=RecordAttributes.SUBNAME
    ),
)


CONTEXT_LINES = Lines(
    Line(
        Item(
            value=['index', 'context.index'],
            label=Label(
                constant="Index",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            )
        ),
    ),
    Line(
        Item(
            value=['parent_index', 'context.parent_index'],
            label=Label(
                constant="Parent Index",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            )
        ),
    ),
    Line(
        Item(
            value=['password', 'context.password'],
            formatter=RecordAttributes.PASSWORD,  # Override
            label=Label(
                constant="Password",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            )
        ),
    ),
    Line(
        Item(
            value=['proxy.method', 'context.proxy.method'],
            formatter=RecordAttributes.METHOD,
        ),
        Item(
            value=['proxy.url', 'context.proxy.url'],
            formatter=RecordAttributes.PROXY,
            wrapper="<%s>"
        ),
        label=Label(
            constant="Proxy",
            delimiter=":",
            formatter=RecordAttributes.LABEL,
        ),
    ),
    Line(
        Item(
            value=['proxy.humanized_state', 'context.proxy.humanized_state'],
            label=Label(
                constant="State",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            ),
        ),
    ),
    Line(
        Item(
            value=["proxy.flattened_error_rate", "context.proxy.flattened_error_rate"],
            label=Label(
                constant="Error Rate (Flat)",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            ),
        ),
    ),
    Line(
        Item(
            value=["proxy.avg_res_time", "context.proxy.avg_res_time"],
            label=Label(
                constant="Avg. Resp Time",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            ),
        ),
    ),
    Line(
        Item(
            value=["proxy.num_active_requests", "context.proxy.num_active_requests"],
            label=Label(
                constant="Num. Requests",
                delimiter=":",
                formatter=RecordAttributes.LABEL,
            ),
        ),
    ),
    formatter=RecordAttributes.CONTEXT_ATTRIBUTE,
)


TRACEBACK_LINE = Line(
    Item(
        value=["frame.filename", "pathname"],
        formatter=RecordAttributes.PATHNAME,
        prefix="(",
        suffix=", "
    ),
    Item(
        value=["frame.function", "funcName"],
        formatter=RecordAttributes.FUNCNAME,
        suffix=", "
    ),
    Item(
        value=["frame.lineno", "lineno"],
        formatter=RecordAttributes.LINENO,
        suffix=")"
    ),
)


BARE_FORMAT_STRING = MESSAGE_LINE
SIMPLE_FORMAT_STRING = PRIMARY_LINE


LOG_FORMAT_STRING = Lines(
    PRIMARY_LINE,
    MESSAGE_LINE,
    Line(
        Item(
            value="other",
            formatter=RecordAttributes.OTHER_MESSAGE
        ),
    ),
    CONTEXT_LINES,
    TRACEBACK_LINE,
    lines_above=1,
    lines_below=0,
    indent=4,
    header=Header(
        char="-",
        length=25,
        label=['level.name'],
        formatter=get_level_formatter,
    )
)
