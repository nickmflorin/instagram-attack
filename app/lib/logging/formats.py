from __future__ import absolute_import

from enum import Enum

from app.lib.utils import Format, Colors, Styles

from .formatter import LogFormattedString, LogFormattedLine, LogItem


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


DATE_FORMAT_OBJ = Format(color=Colors.YELLOW, styles=Styles.DIM)
DATE_FORMAT = DATE_FORMAT_OBJ('%Y-%m-%d %H:%M:%S')


APP_FORMAT = LogFormattedString(
    LogFormattedLine(
        LogItem("{record.channel}", suffix=":", formatter=Colors.GRAY),
        LogItem("{record.level}", suffix=":", formatter=Colors.BLUE),
        LogItem("{record.message}", suffix=":", formatter=Colors.BLACK),
    ),
    LogFormattedLine(
        LogItem("{record.filename}", suffix=", "),
        LogItem("{record.func_name}", suffix=", "),
        LogItem("{record.lineno}", suffix=", ", formatter=Styles.BOLD),
    )
)

TOKEN_TASK_FORMAT = LogFormattedString(
    LogFormattedLine(
        LogItem("{record.channel}", suffix=":", formatter=Colors.GRAY),
        LogItem("{record.level}", suffix=":", formatter=Colors.BLUE),
        LogItem("{record.message}", suffix=":", formatter=Colors.BLACK),
    ),
    LogItem("{record.extra[context].proxy.host}", prefix="Proxy: ",
        formatter=RecordAttributes.PROXY),
    LogFormattedLine(
        LogItem("{record.filename}", suffix=", "),
        LogItem("{record.func_name}", suffix=", "),
        LogItem("{record.lineno}", suffix=", ", formatter=Styles.BOLD),
    )
)

LOGIN_ATTEMPT_FORMAT = LogFormattedString(
    LogFormattedLine(
        LogItem("{record.channel}", suffix=":", formatter=Colors.GRAY),
        LogItem("{record.level}", suffix=":", formatter=Colors.BLUE),
        LogItem("{record.message}", suffix=":", formatter=Colors.BLACK),
    ),
    LogItem("{record.extra[context].password}", prefix="Password: ",
        formatter=RecordAttributes.PASSWORD, indent=4),
    LogItem("{record.extra[context].proxy.host}", prefix="Proxy: ",
        formatter=RecordAttributes.PROXY),
    LogFormattedLine(
        LogItem("{record.filename}", suffix=", "),
        LogItem("{record.func_name}", suffix=", "),
        LogItem("{record.lineno}", suffix=", ", formatter=Styles.BOLD),
    )
)
