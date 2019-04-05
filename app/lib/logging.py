from __future__ import absolute_import

import logging

from enum import Enum
from colorama import init
from colorama import Fore, Style
import traceback

from app.lib.utils import ensure_iterable


__all__ = ('AppLogger', )


RESET_SEQ = "\033[0m"


class FormatEnum(Enum):

    def encode(self, value, reset=True):
        reset_seq = RESET_SEQ if reset else ""
        return "%s%s%s" % (self.value, value, reset_seq)


class Colors(FormatEnum):

    CYAN = Fore.CYAN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    BLUE = Fore.BLUE
    GREEN = Fore.GREEN
    BLACK = Fore.BLACK
    GRAY = "\033[90m"


class Styles(FormatEnum):

    DIM = Style.DIM
    NORMAL = Style.NORMAL
    BRIGHT = Style.BRIGHT
    BOLD = "\033[1m"
    UNDERLINE = '\033[4m'


class Format(object):
    def __init__(self, color=Colors.BLACK, styles=None, wrapper=None):
        self.styles = ensure_iterable(styles or [])
        self.color = color
        self.wrapper = wrapper

    @classmethod
    def reset(cls, text):
        return "%s%s" % (text, RESET_SEQ)

    def __call__(self, text):
        if self.wrapper:
            text = self.wrapper % text
        if self.color or self.styles:
            if self.color:
                text = self.color.encode(text, reset=False)
            for style in self.styles:
                text = style.encode(text, reset=False)
            text = Format.reset(text)
        return text


class LoggingLevels(Enum):

    CRITICAL = (50, Format(color=Colors.RED, styles=[Styles.BRIGHT, Styles.UNDERLINE]))
    ERROR = (40, Format(color=Colors.RED, styles=[Styles.NORMAL, Styles.BRIGHT]))
    WARNING = (30, Format(color=Colors.YELLOW, styles=Styles.NORMAL))
    SUCCESS = (20, Format(color=Colors.GREEN, styles=Styles.NORMAL))
    INFO = (20, Format(color=Colors.CYAN, styles=Styles.DIM))
    DEBUG = (10, Format(color=Colors.BLACK, styles=Styles.NORMAL))

    def __init__(self, code, format):
        self.code = code
        self.format = format

    @classmethod
    def format_record(cls, record):
        level = cls[record.levelname]
        if level in (cls.SUCCESS, cls.ERROR):
            record.msg = level.format(record.msg)
        record.levelname = level.format(record.levelname)


class RecordAttributes(Enum):

    NAME = ('name', None,
        Format(color=Colors.GRAY, styles=Styles.BOLD))
    THREADNAME = ('threadName', None,
        Format(color=Colors.GRAY))
    PROXY = ('proxy', 'host',
        Format(styles=Styles.BOLD, wrapper="<%s>"))
    TOKEN = ('token', None,
        Format(color=Colors.RED, wrapper="%s"))
    RESPONSE = ('response', 'status',
        Format(styles=Styles.BOLD, wrapper="[%s]"))
    STATUS_CODE = ('status_code', None,
        Format(styles=Styles.BOLD, wrapper="[%s]"))
    TASK = ('task', 'name',
        Format(color=Colors.GRAY, styles=Styles.DIM, wrapper="(%s)"))

    def __init__(self, code, attr, format):
        self.code = code
        self.attr = attr
        self.format = format

    @classmethod
    def format_record(cls, record):
        for attribute in cls:
            name = attribute.code
            if hasattr(record, name):
                value = getattr(record, name)

                if not attribute.attr:
                    formatted = attribute.format(value)
                    setattr(record, name, formatted)
                else:
                    if hasattr(value, attribute.attr):
                        value = getattr(value, attribute.attr)
                        if value:
                            formatted = attribute.format(value)
                            setattr(record, name, formatted)
                    else:
                        if type(value) is str or type(value) is int:
                            formatted = attribute.format(value)


class AppLogFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def flatten_items(self, items):
        items = [item for item in items if item]
        items = ["%s" % item for item in items]
        return ' '.join(items)

    def format(self, record):
        if getattr(record, 'isSuccess', None):
            record.levelname = 'SUCCESS'

        LoggingLevels.format_record(record)
        RecordAttributes.format_record(record)

        suffix = self.flatten_items([
            getattr(record, 'status_code', None),
            record.msg,
            getattr(record, 'proxy', None),
            getattr(record, 'token', None),
        ])

        time_prefix = logging.Formatter.format(self, record)

        body = self.flatten_items([
            time_prefix,
            record.levelname,
            record.threadName,
            record.name,
        ])

        return f"{body} : {suffix} ({record.filename}, {Styles.BOLD.encode(record.lineno)})"


class AppLogger(logging.Logger):

    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    FORMAT = (
        "[%(asctime)s]"
    )

    __formatter__ = AppLogFormatter

    def __init__(self, name):
        init(autoreset=True)
        logging.Logger.__init__(self, name, logging.INFO)

        logging.SUCCESS = 25  # between WARNING and INFO
        logging.addLevelName(logging.SUCCESS, 'SUCCESS')

        self.formatter = self.__formatter__(self.FORMAT, datefmt=self.DATE_FORMAT)

        handler = logging.StreamHandler()
        handler.setFormatter(self.formatter)

        self.addHandler(handler)

    def makeRecord(self, name, lvl, fn, lno, msg, args, exc_info, func, extra, sinfo):
        record = super(AppLogger, self).makeRecord(name, lvl, fn, lno, msg, args,
            exc_info, func, extra, sinfo)
        extra = extra or {}
        for key, val in extra.items():
            setattr(record, key, val)
        return record

    def stringify_item(self, key, val):
        bold_value = Styles.BOLD.encode(val)
        return f"{key}: {bold_value}"

    def stringify_items(self, **items):
        string_items = [self.stringify_item(key, val)
            for key, val in items.items()]
        return ' '.join(string_items)

    def items(self, **items):
        self.info(self.stringify_items(**items))

    def success(self, message, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['isSuccess'] = True
        super(AppLogger, self).info(message, *args, **kwargs)

    def exception(self, exc):
        if hasattr(exc, 'message') and exc.message != "":
            content = exc.message
        elif str(exc) != "":
            content = str(exc)
        else:
            content = exc.__class__.__name__

        # NOTE: We can also log the exception directly here with super().exception()
        # but it will still not raise the exception.
        super(AppLogger, self).error(content)

        raise exc.__class__(
            f"{content}"
        )
