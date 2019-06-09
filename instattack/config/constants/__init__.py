from .base import *  # noqa
from .db import *  # noqa
from .http import *  # noqa
from .proxies import *  # noqa
from .users import *  # noqa
from .passwords import *  # noqa

from artsylogger import FormattedEnum, ColorEnum, Format, colors


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOGGER_MODE = 'artsy'


class Colors(ColorEnum):

    GREEN = colors.fg('#28a745')
    LIGHT_GREEN = colors.fg('DarkOliveGreen3')

    RED = colors.fg('#dc3545')
    ALT_RED = colors.fg('Red1')
    LIGHT_RED = colors.fg('IndianRed')

    YELLOW = colors.fg('#F3DB14')
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


class RecordAttributes(FormattedEnum):

    LINE_INDEX = Colors.BLACK.format(bold=True)
    DATETIME = Colors.LIGHT_YELLOW.format(wrapper="[%s]")
    MESSAGE = Colors.BLACK.format()
    OTHER_MESSAGE = Colors.MED_GRAY.format()
    NAME = Colors.GRAY.format()
    SUBNAME = Colors.GRAY.format(bold=True)

    # Exception Messages
    STATUS_CODE = Colors.BLUE.format(bold=True)
    METHOD = Colors.ALT_GRAY.format()
    REASON = Colors.ALT_GRAY.format()

    # Context
    CONTEXT_ATTRIBUTE_1 = Colors.BLACK.format()
    CONTEXT_ATTRIBUTE_2 = Colors.ALT_GRAY.format()
    CONTEXT_ATTRIBUTE_3 = Colors.BLACK.format()

    LABEL = Colors.MED_GRAY.format()

    # Traceback
    PATHNAME = Colors.LIGHT_GRAY.format()
    LINENO = Colors.LIGHT_GRAY.format(bold=True)
    FUNCNAME = Colors.EXTRA_LIGHT_GRAY.format()

    def __init__(self, color):
        FormattedEnum.__init__(self, color)


class Icons:

    CRITICAL = "☠"
    FAIL = ERROR = "✘"
    SUCCESS = "✔"
    STOP = "\u25A3"
    INFO = "ⓘ"
    DEBUG = "⚙️"
    WARNING = "\u26A0"


class LoggingLevels(FormattedEnum):

    CRITICAL = (Colors.RED.format(bold=True), Icons.CRITICAL, 50)
    ERROR = (Colors.RED, Icons.ERROR, 40)
    WARNING = (Colors.YELLOW, Icons.WARNING, 30)
    SUCCESS = (Colors.GREEN, Icons.SUCCESS, 22)
    COMPLETE = (Colors.LIGHT_RED, Icons.SUCCESS, 21)
    INFO = (Colors.BLUE, Icons.INFO, 20)
    DEBUG = (Colors.ALT_GRAY, Icons.DEBUG, 10)

    def __init__(self, color, icon, num):
        FormattedEnum.__init__(self, color, icon=icon, icon_before=True)
        self.num = num
        self.color = color
        self.icon = icon
