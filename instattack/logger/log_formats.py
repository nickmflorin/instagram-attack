from artsylogger import colors, Item, Line, Lines, Header, Label, LineIndex, Format
from datetime import datetime
import logging

from instattack import settings


def get_record_message(record):
    from instattack.src.login.exceptions.utils import get_http_exception_message
    if isinstance(record.msg, Exception):
        return get_http_exception_message(record.msg)
    return record.msg


def get_record_time(record):
    return datetime.now().strftime(settings.DATE_FORMAT)


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

    if getattr(record, 'level_format', None):
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
        value=get_record_message,
        format=get_message_formatter,
        line_index=LineIndex(
            value='line_index',
            format=settings.RecordAttributes.LINE_INDEX
        )
    ),
    indent=1,
)


PRIMARY_LINE = Line(
    Item(
        format=settings.RecordAttributes.DATETIME,
        value=get_record_time,
    ),
    Item(
        value="name",
        format=settings.RecordAttributes.NAME,
        suffix=": "
    ),
    Item(
        value="subname",
        format=settings.RecordAttributes.SUBNAME
    ),
    indent=1,
)


CONTEXT_LINES = Lines(
    Line(
        Item(
            value='password',
            format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_3,
            label=Label(
                constant="Password",
                delimiter=":",
                format=settings.RecordAttributes.LABEL_1,
            )
        ),
        indent=1,
    ),
    Line(
        Item(
            value='proxy.method',
            format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_3,
        ),
        Item(
            value='proxy.url',
            format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_1.format_with_wrapper("<%s>"),
        ),
        label=Label(
            constant="Proxy",
            delimiter=":",
            format=settings.RecordAttributes.LABEL_1,
        ),
        indent=1,
    ),
    Lines(
        Line(
            Item(
                value="proxy.humanized_error_count",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Num. Errors",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                value="proxy.humanized_errors",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Errors",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                value="proxy.humanized_connection_error_count",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Num. Connection Errors",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                value="proxy.humanized_response_error_count",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Num. Response Errors",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                value="proxy.humanized_ssl_error_count",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="Num. SSL Errors",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                value="proxy.num_active_requests",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    constant="# Active Requests",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
    ),
    lines_above=1,
    lines_below=1,
)


TRACEBACK_LINE = Line(
    Item(
        value=["frame.filename", "pathname"],
        format=settings.RecordAttributes.PATHNAME,
        prefix="(",
        suffix=", "
    ),
    Item(
        value=["frame.function", "funcName"],
        format=settings.RecordAttributes.FUNCNAME,
        suffix=", "
    ),
    Item(
        value=["frame.lineno", "lineno"],
        format=settings.RecordAttributes.LINENO,
        suffix=")"
    ),
    indent=1,
)


BARE_FORMAT_STRING = MESSAGE_LINE
SIMPLE_FORMAT_STRING = PRIMARY_LINE


LOG_FORMAT_STRING = Lines(
    PRIMARY_LINE,
    MESSAGE_LINE,
    Line(
        Item(
            value="other",
            format=settings.RecordAttributes.OTHER_MESSAGE
        ),
        indent=1,
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
