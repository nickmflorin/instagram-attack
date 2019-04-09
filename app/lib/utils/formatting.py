from __future__ import absolute_import

from enum import Enum
from colorama import Fore, Style

RESET_SEQ = "\033[0m"


class FormatEnum(Enum):

    def format(self, value, reset=True):
        reset_seq = RESET_SEQ if reset else ""
        return "%s%s%s" % (self.value, value, reset_seq)


class Colors(FormatEnum):

    CYAN = Fore.CYAN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    BLUE = Fore.BLUE
    GREEN = Fore.GREEN
    BLACK = Fore.BLACK
    GRAY = "\033[90m"


class Styles(FormatEnum):

    DIM = Style.DIM
    NORMAL = Style.NORMAL
    BRIGHT = Style.BRIGHT
    BOLD = "\033[1m"
    UNDERLINE = '\033[4m'


class Format(object):
    def __init__(self, color=Colors.BLACK, styles=None, wrapper=None):
        from app.lib.utils import ensure_iterable

        self.styles = ensure_iterable(styles or [])
        self.color = color
        self.wrapper = wrapper

    @classmethod
    def reset(cls, text):
        return "%s%s" % (text, RESET_SEQ)

    def __call__(self, text):
        if self.wrapper:
            text = self.wrapper % text
        if self.color or self.styles:
            if self.color:
                text = self.color.format(text, reset=False)
            for style in self.styles:
                text = style.format(text, reset=False)
            text = Format.reset(text)
        return text


class LoggingLevels(Enum):

    CRITICAL = (50, Format(color=Colors.RED, styles=[Styles.BRIGHT, Styles.UNDERLINE]))
    ERROR = (40, Format(color=Colors.RED, styles=[Styles.NORMAL, Styles.BRIGHT]))
    WARNING = (30, Format(color=Colors.YELLOW, styles=Styles.NORMAL))
    SUCCESS = (20, Format(color=Colors.GREEN, styles=Styles.NORMAL))
    INFO = (20, Format(color=Colors.CYAN, styles=Styles.NORMAL))
    DEBUG = (10, Format(color=Colors.BLACK, styles=Styles.NORMAL))

    def __init__(self, code, format):
        self.code = code
        self.format = format

    def format_message(self, message):
        if self in [LoggingLevels.ERROR, LoggingLevels.SUCCESS, LoggingLevels.CRITICAL]:
            return self.format(message)
        return message


class RecordAttributes(Enum):

    MESSAGE = Format(color=Colors.BLACK, styles=Styles.BOLD)
    HEADER = Format(color=Colors.GRAY, styles=[Styles.DIM, Styles.UNDERLINE])
    NAME = Format(color=Colors.GRAY, styles=Styles.BOLD)
    THREADNAME = Format(color=Colors.GRAY)
    PROXY = Format(styles=Styles.NORMAL, wrapper="<%s>")
    TOKEN = Format(color=Colors.RED)
    STATUS_CODE = Format(styles=Styles.BOLD, wrapper="[%s]")
    METHOD = Format(color=Colors.GRAY, styles=Styles.BOLD)
    TASK = Format(color=Colors.CYAN, styles=Styles.NORMAL, wrapper="(%s)")
    PASSWORD = Format(color=Colors.RED, styles=Styles.NORMAL)

    def __init__(self, format):
        self.format = format
