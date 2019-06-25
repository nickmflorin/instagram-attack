from datetime import datetime
import logging

from instattack import settings

from termx import settings as config
from termx.library import relative_to_app_root
from termx.logging import components


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
    return datetime.now().strftime(settings.DATE_FORMAT)


def get_path_name(record):
    return relative_to_app_root(record.pathname, settings.NAME)


def get_level_formatter():
    def _level_formatter(record):
        level_name = record.levelname.upper()
        fmt = getattr(config.Formats, level_name)
        return fmt.without_icon()
    return _level_formatter


def get_level_color(record):
    level_name = record.levelname.upper()
    fmt = getattr(config.Formats, level_name)
    return fmt.apply_color


def get_message_formatter(record):
    level_name = record.levelname.upper()
    if level_name not in ['DEBUG', 'INFO']:
        fmt = getattr(config.Formats, level_name)
        return fmt
    return config.Text.NORMAL


SIMPLE_FORMAT_STRING = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


MESSAGE_LINES = components.Lines(
    components.Line(
        components.Segment(
            value=get_record_message,
            fmt=get_message_formatter,
        ),
        decoration={
            'prefix': {
                'fmt': config.Text.LIGHT,
                'char': ">",
            }
        }
    ),
    components.Line(
        components.Segment(
            attrs="other",
            fmt=config.Text.MEDIUM,
        ),
        decoration={
            'prefix': {
                'fmt': config.Text.LIGHT,
                'char': ">",
            }
        }
    ),
    decoration={
        'indent': 1,
    }
)


PRIMARY_LINE = components.Lines(
    components.Line(
        components.Segment(
            fmt=config.Text.FADED.copy(wrapper="[%s]"),
            value=get_record_time,
        ),
        components.Segment(
            fmt=get_level_formatter(),
            attrs='levelname',
        ),
        components.Segment(
            attrs="name",
            fmt=config.Text.EMPHASIS,
        ),
        components.Segment(
            attrs="subname",
            fmt=config.Text.PRIMARY.copy(styles=['bold']),
        ),
    ),
)


class DynamicContext(components.DynamicLines):
    """
    [x] TODO:
    ---------
    Figure out a more elegant way of doing this that could involve wrapping
    a generator in a Dynamic() method, that returns a dynamic class.
    """

    def dynamic_child(self, key, val):
        return components.Line(
            components.Segment(
                value=val,
                color=config.Colors.LIGHT_RED,
                label=components.Label(
                    value=key,
                    fmt=config.Text.LIGHT,
                    delimiter=':',
                ),
            ),
            decoration={
                'prefix': {
                    'fmt': config.Text.LIGHT,
                    'char': ">",
                }
            }
        )

    def dynamic_children(self, record):
        if getattr(record, 'data', None) is not None:
            for key, val in record.data.items():
                yield self.dynamic_child(key, val)


CONTEXT_LINES = components.Lines(
    components.Line(
        components.Segment(
            value=get_record_status_code,
            color=config.Colors.LIGHT_RED,
            label=components.Label(
                value="Status Code",
                fmt=config.Text.LIGHT,
                delimiter=':',
            ),
        ),
        decoration={
            'prefix': {
                'fmt': config.Text.LIGHT,
                'char': ">",
            }
        }
    ),
    components.Line(
        components.Segment(
            attrs='password',
            color=config.Colors.LIGHT_RED,
            label=components.Label(
                value="Password",
                delimiter=":",
                fmt=config.Text.LIGHT,
            )
        ),
        decoration={
            'prefix': {
                'fmt': config.Text.LIGHT,
                'char': ">",
            }
        }
    ),
    components.Line(
        components.Segment(
            attrs='proxy.url',
            color=config.Colors.LIGHT_GREEN,
            label=components.Label(
                value="Proxy",
                fmt=config.Text.LIGHT,
                delimiter=':',
            ),
        ),
        decoration={
            'prefix': {
                'fmt': config.Text.LIGHT,
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


TRACEBACK_LINE = components.Lines(
    components.Line(
        components.Segment(
            value=get_path_name,
            fmt=config.Text.EXTRA_LIGHT,
        ),
        components.Segment(
            attrs=["funcName"],
            fmt=config.Text.EXTRA_LIGHT,
        ),
        components.Segment(
            attrs=["lineno"],
            fmt=config.Text.LIGHT,
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


TERMX_FORMAT_STRING = components.LogFormat(
    PRIMARY_LINE,
    MESSAGE_LINES,
    DynamicContext(decoration={
        'indent': 1,
    }),
    CONTEXT_LINES,
    TRACEBACK_LINE,
    width=140,
    lines_above=0,
    lines_below=1,
)
