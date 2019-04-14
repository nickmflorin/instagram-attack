from __future__ import absolute_import

from enum import Enum

from app.lib.utils import Format, Colors, Styles

from .formatter import LogFormattedString, LogFormattedLine, LogLabeledItem, LogItem


class LoggingLevels(Enum):

    CRITICAL = (50, Format(color=Colors.RED, styles=[Styles.BRIGHT, Styles.UNDERLINE]))
    ERROR = (40, Format(color=Colors.RED, styles=[Styles.NORMAL, Styles.BRIGHT]))
    WARNING = (30, Format(color=Colors.YELLOW, styles=Styles.NORMAL))
    NOTICE = (20, Format(color=Colors.GREEN, styles=Styles.NORMAL))
    INFO = (20, Format(color=Colors.CYAN, styles=Styles.NORMAL))
    DEBUG = (10, Format(color=Colors.BLACK, styles=Styles.NORMAL))

    def __init__(self, code, format):
        self.code = code
        self.format = format


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


BASE_FORMAT = LogFormattedLine(
    "\n",
    LogItem("{record.channel}", suffix=":", formatter=Colors.GRAY),
    LogItem("{record.extra[formatted_level_name]}", suffix=" -"),
    LogItem("{record.extra[formatted_message]}"),
    "\n",
)

TRACEBACK_FORMAT = LogFormattedLine(
    LogItem("{record.filename}", suffix=",", formatter=Colors.GRAY),
    LogItem("{record.func_name}", suffix=",", formatter=Colors.GRAY),
    LogItem("{record.lineno}", formatter=Styles.BOLD),
    prefix="(",
    suffix=")"
)

APP_FORMAT = LogFormattedString(
    BASE_FORMAT,
    TRACEBACK_FORMAT
)

TOKEN_TASK_FORMAT = LogFormattedString(
    BASE_FORMAT,
    LogLabeledItem("{record.extra[context].proxy}", label="Proxy",
        formatter=RecordAttributes.PROXY, indent=4),
    "\n",
    TRACEBACK_FORMAT
)

LOGIN_ATTEMPT_FORMAT = LogFormattedString(
    BASE_FORMAT,
    LogLabeledItem("{record.extra[context].password}", label="Password",
        formatter=RecordAttributes.PASSWORD, indent=4),
    "\n",
    LogLabeledItem("{record.extra[context].proxy.host}", label="Proxy",
        formatter=RecordAttributes.PROXY, indent=4),
    "\n",
    TRACEBACK_FORMAT
)
