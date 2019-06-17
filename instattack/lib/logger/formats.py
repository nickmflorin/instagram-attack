from datetime import datetime
import logging

from termx import Formats, Colors
from termx.logging import DynamicLines, Segment, Line, Lines, Header, Label, LogFormat

from instattack.config import constants


def get_record_message(record):
    from instattack.core.exceptions.http import HttpException, get_http_exception_message
    if isinstance(record.msg, Exception):
        if isinstance(record.msg, HttpException):
            message = str(record.msg)
        else:
            message = get_http_exception_message(record.msg)
        return message
    return record.msg


def get_record_status_code(record):
    from instattack.core.exceptions.http import HttpException, get_http_exception_status_code
    if isinstance(record.msg, Exception):
        if isinstance(record.msg, HttpException):
            return record.msg.status_code
        return get_http_exception_status_code(record.msg)


def get_record_time(record):
    return datetime.now().strftime(constants.DATE_FORMAT)


def get_level_formatter():
    def _level_formatter(record):
        level_name = record.levelname.upper()
        return getattr(Formats, level_name)
    return _level_formatter


def get_level_color(record):
    return record.level.colors[0]


def get_message_formatter(record):
    if record.level.name not in ['DEBUG', 'WARNING']:
        return record.level.without_text_decoration().without_wrapper()
    return Formats.TEXT.NORMAL


SIMPLE_FORMAT_STRING = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINES = Lines(
    Line(
        Segment(
            value=get_record_message,
            fmt=get_message_formatter,
        ),
        decoration={
            'prefix': {
                'fmt': Formats.TEXT.LIGHT,
                'char': ">",
            }
        }
    ),
    Line(
        Segment(
            attrs="other",
            fmt=Formats.TEXT.MEDIUM,
        ),
        decoration={
            'prefix': {
                'fmt': Formats.TEXT.LIGHT,
                'char': ">",
            }
        }
    ),
    decoration={
        'indent': 1,
    }
)


PRIMARY_LINE = Lines(
    Line(
        Segment(
            fmt=Formats.TEXT.FADED.new_with(wrapper="[%s]"),
            value=get_record_time,
        ),
        Segment(
            attrs="name",
            fmt=Formats.TEXT.EMPHASIS,
        ),
        Segment(
            attrs="subname",
            fmt=Formats.TEXT.PRIMARY.new_with(styles=['bold']),
        ),
    ),
)


class DynamicContext(DynamicLines):
    """
    [x] TODO:
    ---------
    Figure out a more elegant way of doing this that could involve wrapping
    a generator in a Dynamic() method, that returns a dynamic class.
    """

    def dynamic_child(self, key, val):
        return Line(
            Segment(
                value=val,
                color=Colors.LIGHT_RED,
                label=Label(
                    value=key,
                    fmt=Formats.TEXT.LIGHT,
                    delimiter=':',
                ),
            ),
            decoration={
                'prefix': {
                    'fmt': Formats.TEXT.LIGHT,
                    'char': ">",
                }
            }
        )

    def dynamic_children(self, record):
        if getattr(record, 'data', None) is not None:
            for key, val in record.data.items():
                yield self.dynamic_child(key, val)


CONTEXT_LINES = Lines(
    Line(
        Segment(
            value=get_record_status_code,
            color=Colors.LIGHT_RED,
            label=Label(
                value="Status Code",
                fmt=Formats.TEXT.LIGHT,
                delimiter=':',
            ),
        ),
        decoration={
            'prefix': {
                'fmt': Formats.TEXT.LIGHT,
                'char': ">",
            }
        }
    ),
    Line(
        Segment(
            attrs='password',
            color=Colors.LIGHT_RED,
            label=Label(
                value="Password",
                delimiter=":",
                fmt=Formats.TEXT.LIGHT,
            )
        ),
        decoration={
            'prefix': {
                'fmt': Formats.TEXT.LIGHT,
                'char': ">",
            }
        }
    ),
    Line(
        Segment(
            attrs='proxy.url',
            color=Colors.LIGHT_GREEN,
            label=Label(
                value="Proxy",
                fmt=Formats.TEXT.LIGHT,
                delimiter=':',
            ),
        ),
        decoration={
            'prefix': {
                'fmt': Formats.TEXT.LIGHT,
                'char': ">",
            }
        }
    ),
    lines_above=1,
    lines_below=1,
    decoration={
        'indent': 1,
    }
)


TRACEBACK_LINE = Lines(
    Line(
        Segment(
            attrs=["frame.filename", "pathname"],
            fmt=Formats.TEXT.EXTRA_LIGHT,
        ),
        Segment(
            attrs=["frame.function", "funcName"],
            fmt=Formats.TEXT.EXTRA_LIGHT,
        ),
        Segment(
            attrs=["frame.lineno", "lineno"],
            fmt=Formats.TEXT.LIGHT,
        ),
        decoration={
            'prefix': {
                'char': '(',
                'tight': True,
            },
            'suffix': ')',
            'delimiter': {
                'char': ',',
                'tight': False,
            }
        }
    ),
)


TERMX_FORMAT_STRING = LogFormat(
    PRIMARY_LINE,
    MESSAGE_LINES,
    DynamicContext(decoration={
        'indent': 1,
    }),
    CONTEXT_LINES,
    TRACEBACK_LINE,
    header=Header(
        char="-",
        length=25,
        color=get_level_color,
        label=Label(
            attrs='level.name',
            fmt=get_level_formatter(),
            delimiter=None,
        ),
    ),
    width=140,
    lines_above=0,
    lines_below=1,
)
