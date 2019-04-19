from __future__ import absolute_import

from enum import Enum

from app.lib.formatting import Format, Colors, Styles

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

    LABEL = Format(color=Colors.BLACK, styles=[Styles.DIM, Styles.UNDERLINE])
    MESSAGE = Format(color=Colors.BLACK, styles=Styles.NORMAL)
    CHANNEL = Format(color=Colors.GRAY, styles=Styles.BOLD)
    PROXY = Format(color=Colors.CYAN, wrapper="<%s>")
    TOKEN = Format(color=Colors.CYAN)
    STATUS_CODE = Format(color=Colors.RED, wrapper="[%s]")
    METHOD = Format(color=Colors.CYAN, styles=Styles.NORMAL)
    TASK = Format(color=Colors.CYAN, styles=Styles.NORMAL, wrapper="(%s)")
    PASSWORD = Format(color=Colors.CYAN, styles=Styles.NORMAL)

    def __init__(self, format):
        self.format = format


DATE_FORMAT_OBJ = Format(color=Colors.YELLOW, styles=Styles.DIM)
DATE_FORMAT = DATE_FORMAT_OBJ('%Y-%m-%d %H:%M:%S')


BASE_FORMAT = LogFormattedString(
    LogFormattedLine(
        LogItem("{record.channel}", suffix=":", formatter=RecordAttributes.CHANNEL),
        LogItem("{record.extra[formatted_level_name]}"),
    ),
    "\n",
    LogItem("{record.extra[formatted_message]}", indent=4),
)

TRACEBACK_FORMAT = LogFormattedLine(
    LogItem("{record.filename}", suffix=",", formatter=Colors.GRAY),
    LogItem("{record.func_name}", suffix=",", formatter=Colors.BLACK),
    LogItem("{record.lineno}", formatter=Styles.BOLD),
    prefix="(",
    suffix=")",
    indent=4,
)

APP_FORMAT = LogFormattedString(
    BASE_FORMAT,
    "\n",
    TRACEBACK_FORMAT,
    "\n",
)

TOKEN_TASK_FORMAT = LogFormattedString(
    BASE_FORMAT,
    "\n",
    LogLabeledItem("{record.extra[context].index}", label="Attempt #",
        formatter=Styles.BOLD, indent=8),
    "\n",
    LogLabeledItem("{record.extra[context].proxy[host]}", label="Proxy",
        formatter=RecordAttributes.PROXY, indent=8),
    "\n",
    TRACEBACK_FORMAT,
    "\n",
)


LOGIN_TASK_FORMAT = LogFormattedString(
    BASE_FORMAT,
    "\n",
    LogLabeledItem("{record.extra[context].index}", label="Password #",
        formatter=Styles.BOLD, indent=8),
    "\n",
    LogLabeledItem("{record.extra[context].password}", label="Password",
        formatter=RecordAttributes.PASSWORD, indent=8),
    "\n",
    LogLabeledItem("{record.extra[context].proxy[host]}", label="Proxy",
        formatter=RecordAttributes.PROXY, indent=8),
    "\n",
    TRACEBACK_FORMAT,
    "\n",
)


LOGIN_ATTEMPT_FORMAT = LogFormattedString(
    BASE_FORMAT,
    "\n",
    LogLabeledItem("{record.extra[context].index}", label="Attempt #",
        formatter=Styles.BOLD, indent=8),
    "\n",
    LogLabeledItem("{record.extra[context].parent_index}", label="Password #",
        formatter=Styles.BOLD, indent=8),
    "\n",
    LogLabeledItem("{record.extra[context].password}", label="Password",
        formatter=RecordAttributes.PASSWORD, indent=8),
    "\n",
    LogLabeledItem("{record.extra[context].proxy[host]}", label="Proxy",
        formatter=RecordAttributes.PROXY, indent=8),
    "\n",
    TRACEBACK_FORMAT,
    "\n",
)
