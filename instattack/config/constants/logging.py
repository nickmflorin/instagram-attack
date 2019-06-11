from artsylogger import FormatEnum, Format
from .style import Formats, Icons, Colors


DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOGGER_MODE = 'diagnostics'


class LoggingIcons:

    CRITICAL = Icons.SKULL
    ERROR = Icons.CROSS
    WARNING = Icons.CROSSING
    INFO = Icons.TACK
    DEBUG = Icons.GEAR


class LoggingLevels(FormatEnum):

    CRITICAL = (Formats.State.FAIL.with_bold().with_icon(LoggingIcons.CRITICAL), 50)
    ERROR = (Formats.State.FAIL.with_icon(LoggingIcons.ERROR), 40)
    WARNING = (Formats.State.WARNING.with_icon(LoggingIcons.WARNING), 30)
    INFO = (Format(Colors.BLUE, icon=LoggingIcons.INFO), 20)
    DEBUG = (Formats.Text.MEDIUM.with_icon(LoggingIcons.DEBUG), 10)

    def __init__(self, format, num):
        FormatEnum.__init__(self, format)
        self.num = num
