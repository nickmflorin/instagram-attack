from datetime import datetime
import logging

from artsylogger import Segment, Line, Lines, Header, Label, Format, LogFormat
from instattack.config import constants


def get_record_message(record):
    from instattack.app.exceptions.http import HttpException, get_http_exception_message
    if isinstance(record.msg, Exception):
        if isinstance(record.msg, HttpException):
            return str(record.msg)
        else:
            return get_http_exception_message(record.msg)
    return record.msg


def get_record_status_code(record):
    from instattack.app.exceptions.http import HttpException, get_http_exception_status_code
    if isinstance(record.msg, Exception):
        if isinstance(record.msg, HttpException):
            return record.status_code
        else:
            return get_http_exception_status_code(record.msg)
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
        return record.level
    return _level_formatter


def get_level_color(record):
    return record.level.colors[0]


def get_message_formatter(record):
    if record.level.name not in ['DEBUG', 'WARNING', 'INFO']:
        return record.level.without_text_decoration().without_wrapping()
    return constants.RecordAttributes.MESSAGE


SIMPLE_FORMAT_STRING = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINES = Lines(
    Line(
        Segment(
            value=get_record_message,
            format=get_message_formatter,
        ),
        prefix=constants.Formats.Text.LIGHT("> "),
    ),
    Line(
        Segment(
            attrs="other",
            format=Format(constants.Colors.LIGHT_RED, bold=True)
        ),
        prefix=constants.Formats.Text.LIGHT("> "),
    ),
    Line(
        Segment(
            attrs="other",
            format=constants.RecordAttributes.OTHER_MESSAGE,
        ),
        prefix=constants.Formats.Text.LIGHT("> "),
    ),
    indent=1,
)


PRIMARY_LINE = Lines(
    Line(
        Segment(
            format=constants.RecordAttributes.DATETIME,
            value=get_record_time,
        ),
        Segment(
            attrs="name",
            format=constants.RecordAttributes.NAME,
        ),
        Segment(
            attrs="subname",
            format=constants.RecordAttributes.SUBNAME
        ),
    ),
)


CONTEXT_LINES = Lines(
    Line(
        Segment(
            attrs='password',
            color=constants.Colors.LIGHT_RED,
            label=Label(
                value="Password",
                delimiter=":",
                format=constants.RecordAttributes.LABEL,
            )
        ),
        prefix=constants.Formats.Text.LIGHT(">"),
    ),
    Line(
        Segment(
            attrs='proxy.url',
            color=constants.Colors.LIGHT_RED,
            label=Label(
                value="Proxy",
                delimiter=":",
                format=constants.RecordAttributes.LABEL,
            ),
        ),
        prefix=constants.Formats.Text.LIGHT(">"),
    ),
    Line(
        Segment(
            attrs="proxy.queue_id",
            color=constants.Colors.LIGHT_RED,
            label=Label(
                value="Queue ID",
                delimiter=":",
                format=constants.RecordAttributes.LABEL,
            ),
        ),
        indent=2,
        prefix=constants.Formats.Text.LIGHT(">"),
    ),
    Line(
        Segment(
            attrs="proxy.active_times_used",
            color=constants.Colors.BLACK,
            label=Label(
                value="Times Used",
                delimiter=":",
                format=constants.RecordAttributes.LABEL,
            ),
        ),
        indent=2,
        prefix=constants.Formats.Text.LIGHT(">"),
    ),
    Line(
        Segment(
            attrs="proxy.active_recent_history",
            color=constants.Colors.BLACK,
            prefix=constants.Formats.Text.LIGHT(">"),
            label=Label(
                value="Recent Requests",
                delimiter=":",
                format=constants.RecordAttributes.LABEL,
            ),
        ),
        prefix=constants.Formats.Text.LIGHT("> "),
        indent=2,
    ),
    lines_above=1,
    lines_below=1,
    indent=1,
)


TRACEBACK_LINE = Lines(
    Line(
        Segment(
            attrs=["frame.filename", "pathname"],
            format=constants.RecordAttributes.PATHNAME,
        ),
        Segment(
            attrs=["frame.function", "funcName"],
            format=constants.RecordAttributes.FUNCNAME,
        ),
        Segment(
            attrs=["frame.lineno", "lineno"],
            format=constants.RecordAttributes.LINENO,
        ),
        delimiter=', ',
        prefix="(",
        suffix=")"
    ),
)


LOG_FORMAT_STRING = LogFormat(
    PRIMARY_LINE,
    MESSAGE_LINES,
    CONTEXT_LINES,
    TRACEBACK_LINE,
    header=Header(
        char="-",
        length=25,
        color=get_level_color,
        label=Label(
            attrs='level.name',
            format=get_level_formatter(),
            delimiter=None,
        ),
    ),
    width=140,
    lines_above=0,
    lines_below=1,
)
