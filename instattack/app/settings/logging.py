from plumbum import colors

from instattack.lib.artsylogger import ColorFormatter, AttributeFormatter


SIMPLE_LOGGER = False

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


class Colors(ColorFormatter):

    GREEN = colors.fg('SpringGreen3')
    LIGHT_GREEN = colors.fg('DarkOliveGreen3')

    RED = colors.fg('Red1')
    ALT_RED = colors.fg('Red1')
    LIGHT_RED = colors.fg('IndianRed')

    YELLOW = colors.fg('DarkOrange')
    LIGHT_YELLOW = colors.fg('LightYellow3')

    BLUE = colors.fg('DeepSkyBlue4B')
    ALT_BLUE = colors.fg('CornflowerBlue')
    ALT_BLUE_2 = colors.fg('RoyalBlue1')

    GRAY = colors.fg('Grey7')
    ALT_GRAY = colors.fg('Grey15')
    MED_GRAY = colors.fg('Grey30')
    LIGHT_GRAY = colors.fg('Grey58')
    EXTRA_LIGHT_GRAY = colors.fg('Grey78')

    BLACK = colors.black


class RecordAttributes(AttributeFormatter):

    LINE_INDEX = Colors.BLACK.format(bold=True)
    DATETIME = Colors.LIGHT_YELLOW.format(wrapper="[%s]")
    MESSAGE = Colors.gray(19).format()
    NAME = Colors.ALT_GRAY.format()
    SUBNAME = Colors.GRAY.format(bold=True)
    OTHER_MESSAGE = Colors.MED_GRAY.format()

    # Exception Messages
    STATUS_CODE = Colors.custom('DarkGray').format()
    METHOD = Colors.custom('DarkGray', bold=True)
    REASON = Colors.gray(69).format()

    # Context
    CONTEXT_ATTRIBUTE_1 = Colors.ALT_BLUE.format()
    CONTEXT_ATTRIBUTE_2 = Colors.ALT_GRAY.format()
    CONTEXT_ATTRIBUTE_3 = Colors.ALT_BLUE_2.format()

    LABEL_1 = Colors.GRAY.format()
    LABEL_2 = Colors.LIGHT_GRAY.format()

    # Traceback
    PATHNAME = Colors.LIGHT_GRAY.format()
    LINENO = Colors.LIGHT_GRAY.format(bold=True)
    FUNCNAME = Colors.EXTRA_LIGHT_GRAY.format()


class LoggingLevels(AttributeFormatter):
    CRITICAL = (Colors.RED.format(bold=True, wrapper="☠  %s"), 50)
    ERROR = (Colors.RED.format(bold=False, wrapper="✘  %s"), 40)
    WARNING = (Colors.YELLOW.format(bold=True, wrapper="⚠  %s"), 30)

    SUCCESS = (Colors.GREEN.format(bold=True, wrapper="✔  %s"), 24)
    START = (Colors.LIGHT_GREEN.format(bold=False, wrapper="\u25B6  %s"), 23)
    STOP = (Colors.ALT_RED.format(bold=False, wrapper="\u25A3  %s"), 22)
    COMPLETE = (Colors.LIGHT_RED.format(bold=False, wrapper="✔  %s"), 21)
    INFO = (Colors.BLUE.format(bold=False, wrapper="ⓘ  %s"), 20)

    DEBUG = (Colors.GRAY.format(bold=True, wrapper="✂  %s"), 10)

    def __init__(self, format, num):
        self.format = format
        self.num = num

    @property
    def message_formatter(self):
        return self.format.without_text_decoration().without_wrapping()
