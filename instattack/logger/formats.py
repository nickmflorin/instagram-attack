from __future__ import absolute_import

from enum import Enum

from instattack.utils import Format, Colors, Styles

from .utils import LogItemSet, LogItemLine, LogLabeledItem, LogItem


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
    PROXY = Format(color=Colors.YELLOW, wrapper="<%s>")
    TOKEN = Format(color=Colors.RED)
    STATUS_CODE = Format(color=Colors.RED, wrapper="[%s]")
    METHOD = Format(color=Colors.CYAN, styles=Styles.NORMAL)
    TASK = Format(color=Colors.CYAN, styles=Styles.NORMAL, wrapper="(%s)")
    PASSWORD = Format(color=Colors.BLACK, styles=Styles.BOLD)

    def __init__(self, format):
        self.format = format


DATE_FORMAT_OBJ = Format(color=Colors.YELLOW, styles=Styles.DIM)
DATE_FORMAT = DATE_FORMAT_OBJ('%Y-%m-%d %H:%M:%S')


FORMAT_STRING = LogItemSet(
    LogItemLine(
        LogItem("channel", suffix=":", formatter=RecordAttributes.CHANNEL),
        LogItem("formatted_level_name"),
    ),
    LogItem("formatted_message", indent=4),
    LogItem("other_message", indent=4, formatter=RecordAttributes.MESSAGE),

    LogLabeledItem('index', label="Attempt #",
        formatter=Styles.BOLD, indent=6),
    LogLabeledItem('parent_index', label="Password #",
        formatter=Styles.BOLD, indent=6),
    LogLabeledItem('password', label="Password",
        formatter=RecordAttributes.PASSWORD, indent=6),
    LogLabeledItem('proxy', label="Proxy",
        formatter=RecordAttributes.PROXY, indent=6),

    LogItemLine(
        LogItem("filename", suffix=",", formatter=Colors.GRAY),
        LogItem("lineno", formatter=Styles.BOLD),
        prefix="(",
        suffix=")",
        indent=4,
    )
)
