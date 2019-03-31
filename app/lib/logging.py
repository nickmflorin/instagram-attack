from __future__ import absolute_import

import logging

from enum import Enum
from colorama import init
from colorama import Fore, Style


__all__ = ('SessionLogger', 'EngineLogger', )


RESET_SEQ = "\033[0m"


class Styles(Enum):

    BOLD = "\033[1m"
    UNDERLINE = '\033[4m'
    CYAN = Fore.CYAN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    DIM = Style.DIM
    BLUE = Fore.BLUE
    GREEN = Fore.GREEN

    def encode(self, value):
        return "%s%s%s" % (self.value, value, RESET_SEQ)


class LoggingLevelColors(Enum):

    CRITICAL = (50, Styles.YELLOW)
    ERROR = (40, Styles.RED)
    WARNING = (30, Styles.RED)
    SUCCESS = (20, Styles.GREEN)
    INFO = (20, Styles.CYAN)
    DEBUG = (10, Styles.BLUE)

    def __init__(self, code, style):
        self.code = code
        self.style = style

    @classmethod
    def for_code(cls, code):
        for color in cls:
            if color.code == code:
                return color


class LoggingColors(Enum):

    NAME = ('name', Styles.YELLOW)
    THREADNAME = ('threadName', Styles.DIM)
    # FILENAME = ('fn', Styles.BOLD)

    def __init__(self, record_name, style):
        self.record_name = record_name
        self.style = style

    @classmethod
    def find_for_record_value(cls, record_name):
        for color in cls:
            if color.record_name == record_name:
                return color

    @classmethod
    def format_arg(cls, name, val):
        color = cls.find_for_record_value(name)
        if color:
            return color.style.encode(val)
        else:
            return val


class LogRecordWrapper(dict):

    arg_names = ['name', 'lvl', 'fn', 'lno', 'msg', 'args', 'exc_info', 'func',
        'extra', 'sinfo']

    def __init__(self, *args):
        data = self._convert_args_to_dict(*args)
        super(LogRecordWrapper, self).__init__(data)

    def _convert_args_to_dict(self, *args):
        data = {}
        for i, arg in enumerate(args):
            data[self.arg_names[i]] = arg
        return data

    def format(self):
        for key, val in self.items():
            self[key] = LoggingColors.format_arg(key, val)

    @property
    def args(self):
        data = []
        for arg_name in self.arg_names:
            data.append(self[arg_name])
        return tuple(data)


class AppLogFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def format(self, record):
        try:
            color = LoggingLevelColors[record.levelname]
        except KeyError:
            pass
        else:
            if record.levelname in ("SUCCESS", "ERROR"):
                record.msg = color.style.encode(record.msg)

            record.levelname = color.style.encode(record.levelname)
            record.levelname = Styles.BOLD.encode(record.levelname)

        record.threadName = LoggingColors.THREADNAME.style.encode(record.threadName)
        return logging.Formatter.format(self, record)


class SessionLogFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def format_thread_name(self, record):
        record.threadName = LoggingColors.THREADNAME.style.encode(record.threadName)

    def format_level(self, record):
        color = LoggingLevelColors[record.levelname]

        record.levelname = color.style.encode(record.levelname)
        record.levelname = Styles.BOLD.encode(record.levelname)

    def format_message(self, record):
        color = LoggingLevelColors[record.levelname]

        if record.levelname in ("ERROR", 'SUCCESS'):
            record.msg = color.style.encode(record.msg)

        if hasattr(record, 'url'):
            record.msg += f" ({Styles.UNDERLINE.encode(record.url)})"

        if hasattr(record, 'status_code'):
            record.msg += Styles.BOLD.encode(f" [{record.status_code}]")

    def format(self, record):
        if getattr(record, 'isSuccess', None):
            record.levelname = 'SUCCESS'

        try:
            LoggingLevelColors[record.levelname]
        except KeyError:
            pass
        else:
            self.format_message(record)
            self.format_level(record)

        self.format_thread_name(record)
        return logging.Formatter.format(self, record)


class AppLogger(logging.Logger):

    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
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

    def makeRecord(self, *args, **kwargs):
        wrapper = LogRecordWrapper(*args)
        wrapper.format()
        return super(AppLogger, self).makeRecord(*wrapper.args)

    def success(self, message, extra=None):
        extra = extra or {}
        extra['isSuccess'] = True
        self.info(message, extra=extra)


class EngineLogger(AppLogger):
    """
    These might not necessarily need to be treated differently right now but
    we are eventually going to want to treat them slightly differently.
    """
    FORMAT = (
        "[%(asctime)s] "
        "%(levelname)s "
        "%(threadName)5s - %(name)5s: %(message)s"
    )

    def stringify_item(self, key, val):
        bold_value = Styles.BOLD.encode(val)
        return f"{key}: {bold_value}"

    def stringify_items(self, **items):
        string_items = [self.stringify_item(key, val)
            for key, val in items.items()]
        return ' '.join(string_items)

    def items(self, **items):
        self.info(self.stringify_items(**items))


class SessionLogger(AppLogger):
    """
    These might not necessarily need to be treated differently right now but
    we are eventually going to want to treat them slightly differently.
    """
    __formatter__ = SessionLogFormatter

    FORMAT = (
        "[%(asctime)s] "
        "%(levelname)s "
        "%(threadName)5s - %(name)5s: %(message)s"
    )

    def makeRecord(self, *args, **kwargs):
        wrapper = LogRecordWrapper(*args)
        wrapper.format()
        return super(AppLogger, self).makeRecord(*wrapper.args)
