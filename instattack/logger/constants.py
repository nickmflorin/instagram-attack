from plumbum import colors
from enum import Enum

from .format import Format


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


class LoggingLevels(FormattedEnum):

    CRITICAL = (Format(colors.fg('Red1'), colors.bold, wrapper="[!] %s", format_with_wrapper=True), 50)  # noqa
    ERROR = (Format(colors.fg('Red1'), colors.bold, wrapper="[!] %s", format_with_wrapper=True), 40)
    WARNING = (Format(colors.fg('Gold3A'), colors.bold), 30)
    SUCCESS = (Format(colors.fg('SpringGreen3')), 24)
    START = (Format(colors.fg('DarkOliveGreen3'), wrapper="[+] %s", format_with_wrapper=True), 23)
    STOP = (Format(colors.fg('Red3'), wrapper="[x] %s", format_with_wrapper=True), 22)
    COMPLETE = (Format(colors.fg('IndianRed'), wrapper="[-] %s", format_with_wrapper=True), 21)
    INFO = (Format(colors.fg('DeepSkyBlue4B'), colors.bold), 20)
    DEBUG = (Format(colors.fg('DarkGray'), colors.bold), 10)

    def __init__(self, format, num):
        self.format = format
        self.num = num

    @property
    def message_formatter(self):
        return self.format.without_text_decoration()


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Format(colors.black, wrapper="[%s] ")
    DATETIME = Format(colors.fg('LightYellow3'), wrapper="[%s] ")
    MESSAGE = Format(colors.fg('Grey7'))
    NAME = Format(colors.fg('DarkGray'))
    SUBNAME = Format(colors.black)
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
    FUNCNAME = Format(colors.fg('DarkGray'))
