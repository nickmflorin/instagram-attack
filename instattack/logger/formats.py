from enum import Enum
from plumbum import colors


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class Format(object):
    def __init__(self, *args, wrapper=None, format_with_wrapper=False):
        self.colors = args
        self.wrapper = wrapper
        self.format_with_wrapper = format_with_wrapper

    def __call__(self, text):

        if self.wrapper and self.format_with_wrapper:
            text = self.wrapper % text

        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        # Apply wrapper after styling so we don't style the wrapper.
        text = (c | text)

        if self.wrapper and not self.format_with_wrapper:
            text = self.wrapper % text
        return text

    def without_text_decoration(self):
        undecorated = [c for c in self.colors
            if c not in [colors.underline, colors.bold]]
        return Format(
            *undecorated,
            wrapper=self.wrapper,
            format_with_wrapper=self.format_with_wrapper
        )


class FormattedEnum(Enum):

    def __init__(self, format):
        if isinstance(format, dict):
            self.format = format['base']
            self.formats = format
        else:
            self.format = format
            self.formats = {'base': format}

    def __call__(self, text):
        return self.format(text)


class LoggingLevels(FormattedEnum):

    SUCCESS = {
        'base': Format(colors.fg('SpringGreen3')),
        'other': Format(colors.black),
    }
    START = Format(
        colors.fg('DarkOliveGreen3'),
        wrapper="[+] %s",
        format_with_wrapper=True
    )
    STOP = Format(
        colors.fg('Red3'),
        wrapper="[x] %s",
        format_with_wrapper=True
    )
    COMPLETE = Format(
        colors.fg('IndianRed'),
        wrapper="[-] %s",
        format_with_wrapper=True
    )
    CRITICAL = Format(
        colors.fg('Red1'), colors.bold,
        wrapper="[!] %s",
        format_with_wrapper=True
    )
    ERROR = Format(
        colors.fg('Red1'), colors.bold,
        wrapper="[!] %s",
        format_with_wrapper=True
    )
    WARNING = Format(colors.fg('Gold3A'), colors.bold,)
    INFO = Format(colors.fg('DeepSkyBlue4B'), colors.bold)
    DEBUG = Format(colors.fg('DarkGray'), colors.bold)

    @property
    def message_formatter(self):
        if self in [
            LoggingLevels.SUCCESS,
            LoggingLevels.WARNING,
            LoggingLevels.STOP,
            LoggingLevels.START,
            LoggingLevels.COMPLETE,
            LoggingLevels.CRITICAL
        ]:
            return self.format.without_text_decoration()
        return RecordAttributes.MESSAGE


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Format(colors.black, wrapper="[%s] ")
    DATETIME = Format(colors.fg('LightYellow3'), wrapper="[%s] ")
    MESSAGE = Format(colors.fg('Grey7'))
    NAME = Format(colors.fg('DarkGray'))
    OTHER_MESSAGE = Format(colors.fg('DarkGray'))

    # Exception Messages
    STATUS_CODE = Format(colors.fg('DarkGray'), wrapper="[%s]")
    METHOD = Format(colors.fg('DarkGray'), colors.bold)
    REASON = Format(colors.fg('Grey69'))

    # Context
    TASK = Format(colors.fg('LightBlue'), wrapper="(%s)")
    PASSWORD = Format(colors.fg('Grey69'), colors.bold)
    NUM_REQUESTS = Format(colors.fg('DarkGray'), colors.bold)
    INDEX = Format(colors.fg('Grey69'), colors.bold)
    PROXY = Format(colors.fg('CadetBlueA'), wrapper="<%s>")
    TOKEN = Format(colors.fg('Grey69'))
    LABEL = Format(colors.fg('DarkGray'), wrapper="%s: ")

    # Traceback
    FILENAME = Format(colors.fg('LightGray'))
    LINENO = Format(colors.fg('DarkGray'), colors.bold)
    FUNCNAME = Format(
        colors.fg('DarkGray'),
        format_with_wrapper=True,
        wrapper="def %s",
    )
