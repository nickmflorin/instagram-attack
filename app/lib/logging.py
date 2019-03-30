from __future__ import absolute_import

import logging
import sys

from enum import Enum
from colorama import init
from colorama import Fore, Style


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


class EngineFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def format(self, record):
        try:
            color = LoggingLevelColors[record.levelname]
        except KeyError:
            pass
        else:
            record.levelname = color.style.encode(record.levelname)
        record.threadName = LoggingColors.THREADNAME.style.encode(record.threadName)
        return logging.Formatter.format(self, record)


class EngineLogger(logging.Logger):

    FORMAT = (
        "[%(asctime)s] "
        "%(levelname)s "
        "%(threadName)5s - %(name)5s: %(message)s"
    )

    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(self, name):
        init(autoreset=True)
        logging.Logger.__init__(self, name, logging.INFO)

        self.formatter = EngineFormatter(self.FORMAT, datefmt=self.DATE_FORMAT)

        handler = logging.StreamHandler()
        handler.setFormatter(self.formatter)

        self.addHandler(handler)

    def makeRecord(self, *args, **kwargs):
        wrapper = LogRecordWrapper(*args)
        wrapper.format()
        return super(EngineLogger, self).makeRecord(*wrapper.args)

    def success(self, message):
        print(Styles.GREEN.encode(message))

    def exit(self, message):
        print(Styles.RED.encode(message))
        sys.exit()

    def stringify_item(self, key, val):
        bold_value = Styles.BOLD.encode(val)
        return f"{key}: {bold_value}"

    def stringify_items(self, **items):
        string_items = [self.stringify_item(key, val)
            for key, val in items.items()]
        return ' '.join(string_items)

    def items(self, **items):
        self.info(self.stringify_items(**items))
