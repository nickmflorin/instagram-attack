from __future__ import absolute_import

from enum import Enum
from colorama import Fore, Style

from .utils import ensure_iterable


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
