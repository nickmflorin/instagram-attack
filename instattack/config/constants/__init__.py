from .base import *  # noqa
from .db import *  # noqa
from .http import *  # noqa
from .proxies import *  # noqa
from .users import *  # noqa
from .passwords import *  # noqa

from plumbum import colors
from artsylogger import ColorFormatter, AttributeFormatter


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOGGER_MODE = 'artsy'


class Colors(ColorFormatter):

    GREEN = colors.fg('#28a745')
    LIGHT_GREEN = colors.fg('DarkOliveGreen3')

    RED = colors.fg('#dc3545')
    ALT_RED = colors.fg('Red1')
    LIGHT_RED = colors.fg('IndianRed')

    YELLOW = colors.fg('#ffc107')
    LIGHT_YELLOW = colors.fg('LightYellow3')

    BLUE = colors.fg('#007bff')
    TURQOISE = colors.fg('#17a2b8')
    ALT_BLUE = colors.fg('CornflowerBlue')
    ALT_BLUE_2 = colors.fg('RoyalBlue1')

    INDIGO = colors.fg('#6610f2')
    PURPLE = colors.fg('#6f42c1')
    TEAL = colors.fg('#20c997')
    ORANGE = colors.fg('#ff943b')

    GRAY = colors.fg('Grey7')
    ALT_GRAY = colors.fg('#6c757d')
    MED_GRAY = colors.fg('Grey30')
    LIGHT_GRAY = colors.fg('Grey58')
    EXTRA_LIGHT_GRAY = colors.fg('Grey78')

    BLACK = colors.fg('#343a40')


class RecordAttributes(AttributeFormatter):

    LINE_INDEX = Colors.BLACK.format(bold=True)
    DATETIME = Colors.LIGHT_YELLOW.format(wrapper="[%s]")
    MESSAGE = Colors.BLACK.format()
    OTHER_MESSAGE = Colors.MED_GRAY.format()
    NAME = Colors.PURPLE
    SUBNAME = Colors.GRAY.format(bold=True)

    # Exception Messages
    STATUS_CODE = Colors.BLUE.format(bold=True)
    METHOD = Colors.ALT_GRAY
    REASON = Colors.ALT_GRAY

    # Context
    CONTEXT_ATTRIBUTE_1 = Colors.BLACK.format()
    CONTEXT_ATTRIBUTE_2 = Colors.ALT_GRAY.format()
    CONTEXT_ATTRIBUTE_3 = Colors.BLACK.format()

    LABEL = Colors.MED_GRAY.format()

    # Traceback
    PATHNAME = Colors.LIGHT_GRAY.format()
    LINENO = Colors.LIGHT_GRAY.format(bold=True)
    FUNCNAME = Colors.EXTRA_LIGHT_GRAY.format()


class LoggingLevels(AttributeFormatter):
    CRITICAL = (Colors.RED.format(bold=True, wrapper="☠  %s"), 50)
    ERROR = (Colors.RED.format(bold=False, wrapper="✘  %s"), 40)
    WARNING = (Colors.YELLOW.format(bold=True, wrapper="\u26A0  %s"), 30)
    SUCCESS = (Colors.GREEN.format(bold=True, wrapper="✔  %s"), 24)
    START = (Colors.LIGHT_GREEN.format(bold=False, wrapper="\u25B6  %s"), 23)
    STOP = (Colors.ALT_RED.format(bold=False, wrapper="\u25A3  %s"), 22)
    COMPLETE = (Colors.LIGHT_RED.format(bold=False, wrapper="✔  %s"), 21)
    INFO = (Colors.BLUE.format(bold=False, wrapper="ⓘ  %s"), 20)
    DEBUG = (Colors.ALT_GRAY.format(bold=True, wrapper="✂  %s"), 10)

    def __init__(self, *args):
        self._fmt = args[0]
        self.num = args[1]
