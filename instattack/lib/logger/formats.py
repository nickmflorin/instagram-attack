from __future__ import absolute_import

from enum import Enum
from plumbum import colors

from instattack.lib.utils import (
    LogItemSet, LogItemLine, LogLabeledItem, LogItem, Format)


class FormattedEnum(Enum):

    def __init__(self, format):
        self.format = format

    def __call__(self, text):
        return self.format(text)


class LoggingLevels(FormattedEnum):

    CRITICAL = Format(colors.fg('Magenta'), colors.underline, colors.bold)
    ERROR = Format(colors.fg('Red'), colors.bold)
    WARNING = Format(colors.fg('Orange3'), colors.bold)
    NOTICE = Format(colors.fg('SpringGreen3'), colors.bold)
    INFO = Format(colors.fg('DodgerBlue1'))
    DEBUG = Format(colors.fg('DarkGray'))


class RecordAttributes(FormattedEnum):

    LABEL = Format(colors.black, colors.underline)
    MESSAGE = Format(colors.black)
    SPECIAL_MESSAGE = Format(colors.bg('LightGray'), colors.fg('Magenta'))
    CHANNEL = Format(colors.black, colors.underline)
    PROXY = Format(colors.fg('CadetBlueA'), wrapper="<%s>")
    TOKEN = Format(colors.red)
    STATUS_CODE = Format(colors.red, wrapper="[%s]")
    METHOD = Format(colors.black, colors.bold)
    TASK = Format(colors.fg('LightBlue'), wrapper="(%s)")
    PASSWORD = Format(colors.black, colors.bold)


DATE_FORMAT_OBJ = Format(colors.yellow)
DATE_FORMAT = DATE_FORMAT_OBJ('%Y-%m-%d %H:%M:%S')


def FORMAT_STRING(no_indent=False):

    def opt_indent(val):
        if not no_indent:
            return val
        return 0

    return (
        LogItemSet(
            LogItemLine(
                LogItem("channel", suffix=":", formatter=RecordAttributes.CHANNEL),
                LogItem("formatted_level_name"),
            ),
            LogItem("formatted_message", indent=opt_indent(4)),
            LogItem("other_message", indent=opt_indent(4),
                formatter=RecordAttributes.MESSAGE),

            LogLabeledItem('index', label="Attempt #",
                formatter=Format(colors.bold), indent=opt_indent(6)),
            LogLabeledItem('parent_index', label="Password #",
                formatter=Format(colors.bold), indent=opt_indent(6)),
            LogLabeledItem('password', label="Password",
                formatter=RecordAttributes.PASSWORD, indent=opt_indent(6)),
            LogLabeledItem('proxy', label="Proxy",
                formatter=RecordAttributes.PROXY, indent=opt_indent(6)),

            LogItemLine(
                LogItem("filename", suffix=",", formatter=Format(colors.fg('LightGray'))),
                LogItem("lineno", formatter=Format(colors.bold)),
                prefix="(",
                suffix=")",
                indent=opt_indent(4),
            )
        )
    )
