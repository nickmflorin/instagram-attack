from enum import Enum
from plumbum import colors


class Format(object):
    def __init__(self, *args, wrapper=None):
        self.colors = args
        self.wrapper = wrapper

    def __call__(self, text):
        # TODO: Figure out how to dynamically create color tuples.
        if self.wrapper:
            text = self.wrapper % text

        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        return (c | text)


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