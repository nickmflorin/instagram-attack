from datetime import datetime
import logging

from artsylogger import (
    Item, Line, Lines, Header, Label, LineIndex)
from instattack.config import constants


def get_record_message(record):
    from instattack.app.exceptions.utils import get_http_exception_message
    if isinstance(record.msg, Exception):
        return get_http_exception_message(record.msg)
    return record.msg


def get_record_time(record):
    return datetime.now().strftime(constants.DATE_FORMAT)


def get_level_formatter(without_text_decoration=False, without_wrapping=False):
    """
    TODO:
    ----
    This can probably be simplified now that we have a new general framework for
    the format object.
    """
    def _level_formatter(record):
        fmt = record.level.format()

        if without_text_decoration and without_wrapping:
            return fmt.without_text_decoration().without_wrapping()
        elif without_text_decoration:
            return fmt.without_text_decoration()
        elif without_wrapping:
            return fmt.without_wrapping()
        else:
            return fmt
    return _level_formatter


def get_level_color(record):
    fmt = record.level.format()
    return fmt.colors[0]


def get_message_formatter(record):
    if record.level.name not in ['DEBUG', 'WARNING', 'INFO']:
        fmt = record.level.format()
        return fmt.without_text_decoration().without_wrapping()
    return constants.RecordAttributes.MESSAGE


SIMPLE_FORMAT_STRING = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINE = Line(
    Item(
        value=get_record_message,
        format=get_message_formatter,
        line_index=LineIndex(
            attrs='line_index',
            format=constants.RecordAttributes.LINE_INDEX
        )
    ),
    indent=1,
)


PRIMARY_LINE = Line(
    Item(
        format=constants.RecordAttributes.DATETIME,
        value=get_record_time,
    ),
    Item(
        attrs="name",
        format=constants.RecordAttributes.NAME,
        suffix=": "
    ),
    Item(
        attrs="subname",
        format=constants.RecordAttributes.SUBNAME
    ),
    indent=1,
)


CONTEXT_LINES = Lines(
    Line(
        Item(
            attrs='password',
            format=constants.RecordAttributes.CONTEXT_ATTRIBUTE_3,
            label=Label(
                value="Password",
                delimiter=":",
                format=constants.RecordAttributes.LABEL,
            )
        ),
        indent=1,
    ),
    Line(
        Item(
            attrs='proxy.method',
            format=constants.RecordAttributes.CONTEXT_ATTRIBUTE_3,
        ),
        Item(
            attrs='proxy.url',
            format=constants.RecordAttributes.CONTEXT_ATTRIBUTE_1,
        ),
        label=Label(
            value="Proxy",
            delimiter=":",
            format=constants.RecordAttributes.LABEL,
        ),
        indent=1,
    ),
    Lines(
        Line(
            Item(
                attrs="proxy.queue_id",
                format=constants.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    value="Queue ID",
                    delimiter=":",
                    format=constants.RecordAttributes.LABEL,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                attrs="proxy.active_times_used",
                format=constants.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    value="Times Used",
                    delimiter=":",
                    format=constants.RecordAttributes.LABEL,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                attrs="proxy.active_recent_history",
                format=constants.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                label=Label(
                    value="Recent Requests",
                    delimiter=":",
                    format=constants.RecordAttributes.LABEL,
                ),
            ),
            indent=2,
        ),
    ),
    lines_above=1,
    lines_below=1,
)


THREAD_LINE = Line(
    Item(
        attrs=["thread"],
        format=constants.RecordAttributes.FUNCNAME,
        prefix="(",
        suffix=", "
    ),
    Item(
        attrs=["threadName"],
        format=constants.RecordAttributes.PATHNAME,
        suffix=")"
    ),
    indent=1,
)

TRACEBACK_LINE = Line(
    Item(
        attrs=["frame.filename", "pathname"],
        format=constants.RecordAttributes.PATHNAME,
        prefix="(",
        suffix=", "
    ),
    Item(
        attrs=["frame.function", "funcName"],
        format=constants.RecordAttributes.FUNCNAME,
        suffix=", "
    ),
    Item(
        attrs=["frame.lineno", "lineno"],
        format=constants.RecordAttributes.LINENO,
        suffix=")"
    ),
    indent=1,
)


LOG_FORMAT_STRING = Lines(
    PRIMARY_LINE,
    MESSAGE_LINE,
    Line(
        Item(
            attrs="other",
            format=constants.RecordAttributes.OTHER_MESSAGE
        ),
        indent=1,
    ),
    CONTEXT_LINES,
    THREAD_LINE,
    TRACEBACK_LINE,
    lines_above=0,
    lines_below=1,
    header=Header(
        char="-",
        length=25,
        color='level.color',
        label=Label(
            attrs='level.name',
            format=get_level_formatter(),
            delimiter=None,
        ),
    )
)
