from artsylogger import FormatEnum, Format
from .style import Formats, Icons, Colors


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOGGER_MODE = 'artsy'


class LoggingIcons:

    CRITICAL = Icons.SKULL
    ERROR = Icons.CROSS
    WARNING = Icons.CROSSING
    INFO = Icons.TACK
    DEBUG = Icons.GEAR


class RecordAttributes(FormatEnum):

    DATETIME = Formats.Text.FADED.with_wrapper("[%s]")
    MESSAGE = Formats.Text.NORMAL
    OTHER_MESSAGE = Formats.Text.MEDIUM
    NAME = Formats.Text.PRIMARY
    SUBNAME = Formats.Text.PRIMARY.with_bold()

    # Exception Messages
    STATUS_CODE = Format(Colors.BLUE).with_bold()
    LABEL = Formats.Text.MEDIUM

    # Traceback
    PATHNAME = Formats.Text.EXTRA_LIGHT
    LINENO = Formats.Text.LIGHT
    FUNCNAME = Formats.Text.EXTRA_LIGHT


class LoggingLevels(FormatEnum):

    CRITICAL = (Formats.State.FAIL.with_bold().with_icon(LoggingIcons.CRITICAL), 50)
    ERROR = (Formats.State.FAIL.with_icon(LoggingIcons.ERROR), 40)
    WARNING = (Formats.State.WARNING.with_icon(LoggingIcons.WARNING), 30)
    INFO = (Format(Colors.BLUE, icon=LoggingIcons.INFO), 20)
    DEBUG = (Formats.Text.MEDIUM.with_icon(LoggingIcons.DEBUG), 10)

    def __init__(self, format, num):
        FormatEnum.__init__(self, format)
        self.num = num
