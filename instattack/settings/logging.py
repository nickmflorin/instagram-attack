from plumbum import colors
from enum import Enum

from artsylogger import Format


SIMPLE_LOGGER = False

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


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

    @property
    def colors(self):
        return self.format.colors

    def format_with_wrapper(self, wrapper, format_with_wrapper=False):
        return Format(*self.colors,
            wrapper=wrapper, format_with_wrapper=format_with_wrapper)


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Format(colors.black, colors.bold)
    DATETIME = Format(colors.fg('LightYellow3'), wrapper="[%s]")
    MESSAGE = Format(colors.fg('Grey19'))
    NAME = Format(colors.fg('Grey15'))
    SUBNAME = Format(colors.fg('Grey7'), colors.bold)
    OTHER_MESSAGE = Format(colors.fg('Grey30'))

    # Exception Messages
    STATUS_CODE = Format(colors.fg('DarkGray'))
    METHOD = Format(colors.fg('DarkGray'), colors.bold)
    REASON = Format(colors.fg('Grey69'))

    # Context
    CONTEXT_ATTRIBUTE_1 = Format(colors.fg('CornflowerBlue'))
    CONTEXT_ATTRIBUTE_2 = Format(colors.fg('Grey15'))
    CONTEXT_ATTRIBUTE_3 = Format(colors.fg('RoyalBlue1'))

    LABEL_1 = Format(colors.fg('Grey7'))
    LABEL_2 = Format(colors.fg('Grey58'))

    # Traceback
    PATHNAME = Format(colors.fg('Grey58'))
    LINENO = Format(colors.fg('Grey58'), colors.bold)
    FUNCNAME = Format(colors.fg('Grey78'))


class LoggingLevels(FormattedEnum):

    CRITICAL = (Format(colors.fg('Red1'), colors.bold,
        wrapper="[!] %s", format_with_wrapper=True), 50)  # noqa
    ERROR = (Format(colors.fg('Red1'), colors.bold,
        wrapper="[!] %s", format_with_wrapper=True), 40)
    WARNING = (Format(colors.fg('SandyBrown'), colors.bold,
        wrapper="[!] %s", format_with_wrapper=True), 30)
    SUCCESS = (Format(colors.fg('SpringGreen3'),
        wrapper="[$] %s", format_with_wrapper=True), 24)
    START = (Format(colors.fg('DarkOliveGreen3'),
        wrapper="[+] %s", format_with_wrapper=True), 23)
    STOP = (Format(colors.fg('Red3'),
        wrapper="[x] %s", format_with_wrapper=True), 22)
    COMPLETE = (Format(colors.fg('IndianRed'),
        wrapper="[-] %s", format_with_wrapper=True), 21)
    INFO = (Format(colors.fg('DeepSkyBlue4B'), colors.bold,
        wrapper="[i] %s", format_with_wrapper=True), 20)
    DEBUG = (Format(colors.fg('DarkGray'), colors.bold,
        wrapper="[ ] %s", format_with_wrapper=True), 10)

    def __init__(self, format, num):
        self.format = format
        self.num = num

    @property
    def message_formatter(self):
        return self.format.without_text_decoration().without_wrapping()
