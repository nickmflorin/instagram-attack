from datetime import datetime
import logging

from artsylogger import (
    Item, Line, Lines, Header, Label, LineIndex)
from instattack.config import settings


def get_proxy_last_error(record):
    if getattr(record, 'proxy', None):
        proxy = record.proxy
        active_errors = proxy.requests(fail=True, active=True)
        if active_errors:
            return active_errors[-1].error


def get_record_message(record):
    from instattack.app.exceptions.utils import get_http_exception_message
    if isinstance(record.msg, Exception):
        return get_http_exception_message(record.msg)
    return record.msg


def get_record_time(record):
    return datetime.now().strftime(settings.DATE_FORMAT)


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


def get_message_formatter(record):
    fmt = record.level.format()
    return fmt.without_text_decoration().without_wrapping()


SIMPLE_FORMATTER = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINE = Line(
    Item(
        value=get_record_message,
        format=get_message_formatter,
        line_index=LineIndex(
            attrs='line_index',
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
        attrs="name",
        format=settings.RecordAttributes.NAME,
        suffix=": "
    ),
    Item(
        attrs="subname",
        format=settings.RecordAttributes.SUBNAME
    ),
    indent=1,
)


CONTEXT_LINES = Lines(
    Line(
        Item(
            attrs='password',
            format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_3,
            label=Label(
                value="Password",
                delimiter=":",
                format=settings.RecordAttributes.LABEL_1,
            )
        ),
        indent=1,
    ),
    Line(
        Item(
            attrs='proxy.method',
            format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_3,
        ),
        Item(
            attrs='proxy.url',
            format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_1.format(wrapper="<%s>"),
        ),
        label=Label(
            value="Proxy",
            delimiter=":",
            format=settings.RecordAttributes.LABEL_1,
        ),
        indent=1,
    ),
    Lines(
        # Line(
        #     Item(
        #         attrs="proxy.humanized_active_errors",
        #         format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
        #         label=Label(
        #             value="Active Errors",
        #             delimiter=":",
        #             format=settings.RecordAttributes.LABEL_2,
        #         ),
        #     ),
        #     indent=2,
        # ),
        Line(
            Item(
                attrs="proxy.queue_id",
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                # Will only show if as None if any other item in group is non-null
                label=Label(
                    value="Queue ID",
                    delimiter=":",
                    format=settings.RecordAttributes.LABEL_2,
                ),
            ),
            indent=2,
        ),
        Line(
            Item(
                value=get_proxy_last_error,
                format=settings.RecordAttributes.CONTEXT_ATTRIBUTE_2,
                # Will only show if as None if any other item in group is non-null
                label=Label(
                    value="Last Error",
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
        attrs=["frame.filename", "pathname"],
        format=settings.RecordAttributes.PATHNAME,
        prefix="(",
        suffix=", "
    ),
    Item(
        attrs=["frame.function", "funcName"],
        format=settings.RecordAttributes.FUNCNAME,
        suffix=", "
    ),
    Item(
        attrs=["frame.lineno", "lineno"],
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
            attrs="other",
            format=settings.RecordAttributes.OTHER_MESSAGE
        ),
        indent=1,
    ),
    CONTEXT_LINES,
    TRACEBACK_LINE,
    lines_above=0,
    lines_below=1,
    header=Header(
        char="-",
        length=25,
        label=Label(
            attrs='level.name',
            format=get_level_formatter(),
            delimiter=None,
        ),
        format=get_level_formatter(without_wrapping=True, without_text_decoration=True),
    )
)
