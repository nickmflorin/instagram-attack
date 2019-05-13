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
        self.format = format

    def __call__(self, text):
        return self.format(text)


class LoggingLevels(FormattedEnum):

    NOTE = Format(colors.fg('LightGray'))
    START = Format(
        colors.fg('CadetBlueA'),
        wrapper="[+] %s",
        format_with_wrapper=True
    )
    STOP = Format(
        colors.fg('Red3'),
        wrapper="[x] %s",
        format_with_wrapper=True
    )
    COMPLETE = Format(
        colors.fg('DarkOliveGreen3'),
        wrapper="[-] %s",
        format_with_wrapper=True
    )
    CRITICAL = Format(
        colors.fg('Red1'), colors.bold,
        wrapper="[!] %s",
        format_with_wrapper=True
    )
    ERROR = Format(
        colors.fg('Red'), colors.underline,
        wrapper="[!] %s",
        format_with_wrapper=True
    )
    WARNING = Format(colors.fg('Gold3A'))
    NOTICE = Format(colors.fg('LightSkyBlue3A'))
    INFO = Format(colors.fg('DeepSkyBlue4B'))
    DEBUG = Format(colors.fg('DarkGray'))

    @property
    def message_formatter(self):
        return self.format.without_text_decoration()


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Format(colors.black, wrapper="[%s] ")
    DATETIME = Format(colors.fg('LightYellow3'), wrapper="[%s] ")
    LABEL = Format(colors.fg('DarkGray'), wrapper="%s: ")
    OTHER_MESSAGE = Format(colors.fg('Grey69'))
    SPECIAL_MESSAGE = Format(colors.bg('LightGray'), colors.fg('Magenta'))
    NAME = Format(colors.fg('DarkGray'))
    PROXY = Format(colors.fg('CadetBlueA'), wrapper="<%s>")
    TOKEN = Format(colors.red)
    STATUS_CODE = Format(colors.fg('DarkGray'), wrapper="[%s]")
    METHOD = Format(colors.fg('DarkGray'), colors.bold)
    REASON = Format(colors.fg('DarkGray'))
    TASK = Format(colors.fg('LightBlue'), wrapper="(%s)")
    PASSWORD = Format(colors.black, colors.bold)
