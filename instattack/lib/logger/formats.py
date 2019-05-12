from enum import Enum
from plumbum import colors


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class Format(object):
    def __init__(self, *args, wrapper=None):
        self.colors = args
        self.wrapper = wrapper

    def __call__(self, text):
        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        # Apply wrapper after styling so we don't style the wrapper.
        text = (c | text)
        if self.wrapper:
            text = self.wrapper % text
        return text


class FormattedEnum(Enum):

    def __init__(self, format):
        self.format = format

    def __call__(self, text):
        return self.format(text)


class LoggingLevels(FormattedEnum):

    START = Format(colors.fg('RosyBrown'), colors.bold)
    COMPLETE = Format(colors.fg('Green'), colors.bold)
    CRITICAL = Format(colors.fg('Magenta'), colors.bold)
    ERROR = Format(colors.fg('Red'), colors.underline)
    WARNING = Format(colors.fg('Gold3A'), colors.bold)
    NOTICE = Format(colors.fg('LightSkyBlue3A'), colors.bold)
    INFO = Format(colors.fg('DeepSkyBlue2'), colors.bold)
    DEBUG = Format(colors.fg('DarkGray'), colors.bold)

    @property
    def message_formatter(self):
        return Format(self.format.colors[0])


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Format(colors.black, wrapper="[%s] ")
    DATETIME = Format(colors.fg('LightYellow3'), wrapper="[%s] ")
    LABEL = Format(colors.fg('DarkGray'), colors.bold, wrapper="%s: ")
    OTHER_MESSAGE = Format(colors.fg('Grey69'))
    SPECIAL_MESSAGE = Format(colors.bg('LightGray'), colors.fg('Magenta'))
    NAME = Format(colors.fg('Grey3'))
    PROXY = Format(colors.fg('CadetBlueA'), wrapper="<%s>")
    TOKEN = Format(colors.red)
    STATUS_CODE = Format(colors.red, wrapper="[%s]")
    METHOD = Format(colors.black, colors.bold)
    TASK = Format(colors.fg('LightBlue'), wrapper="(%s)")
    PASSWORD = Format(colors.black, colors.bold)
