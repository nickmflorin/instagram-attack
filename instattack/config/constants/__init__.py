from .base import *  # noqa
from .db import *  # noqa
from .http import *  # noqa
from .proxies import *  # noqa
from .users import *  # noqa
from .passwords import *  # noqa

from artsylogger import FormatEnum, ColorEnum, Format, colors


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOGGER_MODE = 'artsy'


class Colors(ColorEnum):

    GREEN = colors.fg('#28a745')
    LIGHT_GREEN = colors.fg('DarkOliveGreen3')

    RED = colors.fg('#dc3545')
    ALT_RED = colors.fg('Red1')
    LIGHT_RED = colors.fg('IndianRed')

    YELLOW = colors.fg('Gold3')
    LIGHT_YELLOW = colors.fg('LightYellow3')

    BLUE = colors.fg('#007bff')
    DARK_BLUE = colors.fg('#336699')
    TURQOISE = colors.fg('#17a2b8')
    ALT_BLUE = colors.fg('CornflowerBlue')
    ALT_BLUE_2 = colors.fg('RoyalBlue1')

    INDIGO = colors.fg('#6610f2')
    PURPLE = colors.fg('#364652')
    TEAL = colors.fg('#20c997')
    ORANGE = colors.fg('#EDAE49')

    GRAY = colors.fg('#393E41')
    ALT_GRAY = colors.fg('#6c757d')
    MED_GRAY = colors.fg('Grey30')
    LIGHT_GRAY = colors.fg('Grey58')
    EXTRA_LIGHT_GRAY = colors.fg('Grey78')

    BLACK = colors.fg('#232020')
    BROWN = colors.fg('#493B2A')
    HEAVY_BLACK = colors.black


class RecordAttributes(FormatEnum):

    LINE_INDEX = Format(Colors.BLACK.value, colors.bold)
    DATETIME = Format(Colors.LIGHT_YELLOW.value, wrapper="[%s]")
    MESSAGE = Format(Colors.GRAY.value)
    OTHER_MESSAGE = Format(Colors.MED_GRAY.value)
    NAME = Format(Colors.GRAY.value)
    SUBNAME = Format(Colors.GRAY.value, colors.bold)

    # Exception Messages
    STATUS_CODE = Format(Colors.BLUE.value, colors.bold)
    METHOD = Format(Colors.ALT_GRAY.value)
    REASON = Format(Colors.ALT_GRAY.value)

    # Context
    CONTEXT_ATTRIBUTE_1 = Format(Colors.BLACK.value)
    CONTEXT_ATTRIBUTE_2 = Format(Colors.ALT_GRAY.value)
    CONTEXT_ATTRIBUTE_3 = Format(Colors.BLACK.value)

    LABEL = Format(Colors.MED_GRAY.value)

    # Traceback
    PATHNAME = Format(Colors.EXTRA_LIGHT_GRAY.value)
    LINENO = Format(Colors.LIGHT_GRAY.value)
    FUNCNAME = Format(Colors.EXTRA_LIGHT_GRAY.value)


class Icons:

    CRITICAL = "☠"
    FAIL = ERROR = "✘"
    SUCCESS = "✔"
    STOP = "\u25A3"
    INFO = "📍"
    DEBUG = "⚙️ "
    WARNING = "🚸"


class LoggingLevels(FormatEnum):

    CRITICAL = (Colors.RED.format_with(colors.bold, icon=Icons.CRITICAL), 50)
    ERROR = (Colors.RED.format_with(icon=Icons.ERROR), 40)
    WARNING = (Colors.YELLOW.format_with(icon=Icons.WARNING), 30)
    SUCCESS = (Colors.GREEN.format_with(icon=Icons.SUCCESS), 22)
    COMPLETE = (Colors.LIGHT_RED.format_with(icon=Icons.SUCCESS), 21)
    INFO = (Colors.BLUE.format_with(icon=Icons.INFO), 20)
    DEBUG = (Colors.ALT_GRAY.format_with(icon=Icons.DEBUG), 10)

    def __init__(self, format, num):
        FormatEnum.__init__(self, format)
        self.num = num
