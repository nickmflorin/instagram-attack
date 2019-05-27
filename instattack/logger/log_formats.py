from artsylogger import colors, Item, Line, Lines, Header, Label, LineIndex, Format
from datetime import datetime
import logging

from .constants import RecordAttributes, DATE_FORMAT
from .utils import (
    get_record_request_method, get_record_status_code, get_record_message,
    get_record_response_reason)


def get_record_time(record):
    return datetime.now().strftime(DATE_FORMAT)


def get_level_formatter(without_text_decoration=False, without_wrapping=False):
    def _level_formatter(record):
        if getattr(record, 'color', None):
            if without_text_decoration:
                return Format(record.color)
            else:
                return Format(record.color, colors.bold)
        else:
            format = record.level.format
            if without_text_decoration:
                format = format.without_text_decoration()
            if without_wrapping:
                format = format.without_wrapping()
            return format
    return _level_formatter


def get_message_formatter(record):

    if getattr(record, 'highlight', None):
        return RecordAttributes.SPECIAL_MESSAGE
    elif getattr(record, 'level_format', None):
        return record.level_format.message_formatter
    elif getattr(record, 'color', None):
        return Format(record.color)
    else:
        return record.level.message_formatter


SIMPLE_FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINE = Line(
    Item(
        value=get_record_request_method,
        format=RecordAttributes.METHOD,
        suffix=": "
    ),
    Item(
        value=get_record_response_reason,
        format=RecordAttributes.REASON,
        suffix=" - ",
    ),
    Item(
        value=get_record_message,
        format=get_message_formatter,
        line_index=LineIndex(
            value='line_index',
            format=RecordAttributes.LINE_INDEX
        )
    ),
    Item(
        value=get_record_status_code,
        format=RecordAttributes.STATUS_CODE,
    ),
    indent=2,
)


PRIMARY_LINE = Line(
    Item(
        format=RecordAttributes.DATETIME,
        value=get_record_time,
    ),
    Item(
        value="name",
        format=RecordAttributes.NAME,
        suffix=": "
    ),
    Item(
        value="subname",
        format=RecordAttributes.SUBNAME
    ),
    indent=2,
)


CONTEXT_LINES = Lines(
    Line(
        Item(
            value='password',
            format=RecordAttributes.CONTEXT_ATTRIBUTE_3,
            label=Label(
                constant="Password",
                delimiter=":",
                format=RecordAttributes.LABEL_1,
            )
        ),
        indent=2,
    ),
    Line(
        Item(
            value='proxy.method',
            format=RecordAttributes.CONTEXT_ATTRIBUTE_3,
        ),
        Item(
            value='proxy.url',
            format=Format(
                RecordAttributes.CONTEXT_ATTRIBUTE_1.format.colors,
                wrapper="<%s>"
            )
        ),
        label=Label(
            constant="Proxy",
            delimiter=":",
            format=RecordAttributes.LABEL_1,
        ),
        indent=2,
    ),
    Lines(
        Line(
            Item(
                value="proxy.error_count",
                format=RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Num. Errors",
                    delimiter=":",
                    format=RecordAttributes.LABEL_2,
                ),
            ),
            indent=4,
        ),
        Line(
            Item(
                value="proxy.num_connection_errors",
                format=RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Num. Connection Errors",
                    delimiter=":",
                    format=RecordAttributes.LABEL_2,
                ),
            ),
            indent=4,
        ),
        Line(
            Item(
                value="proxy.humanized_errors",
                format=RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Errors",
                    delimiter=":",
                    format=RecordAttributes.LABEL_2,
                ),
            ),
            indent=4,
        ),
        Line(
            Item(
                value="proxy.num_active_requests",
                format=RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="# Active Requests",
                    delimiter=":",
                    format=RecordAttributes.LABEL_2,
                ),
            ),
            indent=4,
        ),
    ),
    lines_above=1,
    lines_below=1,
)


TRACEBACK_LINE = Line(
    Item(
        value=["frame.filename", "pathname"],
        format=RecordAttributes.PATHNAME,
        prefix="(",
        suffix=", "
    ),
    Item(
        value=["frame.function", "funcName"],
        format=RecordAttributes.FUNCNAME,
        suffix=", "
    ),
    Item(
        value=["frame.lineno", "lineno"],
        format=RecordAttributes.LINENO,
        suffix=")"
    ),
    indent=2,
)


BARE_FORMAT_STRING = MESSAGE_LINE
SIMPLE_FORMAT_STRING = PRIMARY_LINE


LOG_FORMAT_STRING = Lines(
    PRIMARY_LINE,
    MESSAGE_LINE,
    Line(
        Item(
            value="other",
            format=RecordAttributes.OTHER_MESSAGE
        ),
        indent=2,
    ),
    CONTEXT_LINES,
    TRACEBACK_LINE,
    lines_above=1,
    lines_below=0,
    header=Header(
        char="-",
        length=25,
        label=Label(
            value='level.name',
            format=get_level_formatter(without_text_decoration=True),
        ),
        format=get_level_formatter(without_wrapping=True, without_text_decoration=True),
    )
)
