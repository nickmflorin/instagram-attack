from __future__ import absolute_import

import logging

from enum import Enum
from colorama import init
from colorama import Fore, Style

import app.lib.exceptions as exceptions
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
    def __init__(self, color=Colors.BLACK, styles=None):
        self.styles = ensure_iterable(styles or [])
        self.color = color

    @classmethod
    def reset(cls, text):
        return "%s%s" % (text, RESET_SEQ)

    def __call__(self, text):
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
    def for_code(cls, code):
        try:
            return [color for color in cls if color.code == code][0]
        except IndexError:
            raise ValueError(f"Invalid log level code {code}.")


class RecordAttributes(Enum):

    NAME = ('name', Format(color=Colors.GRAY, styles=Styles.BOLD))
    THREADNAME = ('threadName', Format(color=Colors.GRAY))
    # FILENAME = ('fn', Styles.BOLD)

    def __init__(self, code, format):
        self.code = code
        self.format = format

    @classmethod
    def for_code(cls, code):
        try:
            return [attr for attr in cls if attr.code == code][0]
        except IndexError:
            raise ValueError(f"Invalid log level code {code}.")


class LogRecordWrapper(dict):

    arg_names = ['name', 'lvl', 'fn', 'lno', 'msg', 'args', 'exc_info', 'func',
        'extra', 'sinfo']

    def __init__(self, *args):
        data = self._convert_args_to_dict(*args)
        super(LogRecordWrapper, self).__init__(data)

    def format(self):
        for key, val in self.items():
            try:
                attribute = RecordAttributes.for_code(key)
            except ValueError:
                pass
            else:
                self[key] = attribute.format(val)

    def _convert_args_to_dict(self, *args):
        data = {}
        for i, arg in enumerate(args):
            data[self.arg_names[i]] = arg
        return data

    @property
    def args(self):
        data = []
        for arg_name in self.arg_names:
            data.append(self[arg_name])
        return tuple(data)


class AppLogFormatter(logging.Formatter):

    def __init__(self, msg, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)

    def format_message(self, record):
        if record.levelname in ("ERROR", 'SUCCESS'):
            record.msg = LoggingLevels[record.levelname].format(record.msg)

    def format(self, record):
        if getattr(record, 'isSuccess', None):
            record.levelname = 'SUCCESS'

        level = LoggingLevels[record.levelname]

        self.format_message(record)

        record.levelname = level.format(record.levelname)
        record.threadName = RecordAttributes.THREADNAME.format(record.threadName)

        if hasattr(record, 'status_code'):
            record.msg += Styles.BOLD.encode(f" [{record.status_code}]")

        if hasattr(record, 'proxy'):
            record.msg += f" <{Styles.BOLD.encode(record.proxy.ip)}>"

        if hasattr(record, 'result'):
            record.msg += f" ({Styles.BOLD.encode(record.result.error_type)})"
            record.msg += f" ({Styles.BOLD.encode(record.result.error_message)})"

        return logging.Formatter.format(self, record)


class AppLogger(logging.Logger):

    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    FORMAT = (
        "[%(asctime)s] "
        "%(levelname)s "
        "%(threadName)5s - %(name)5s: %(message)s"
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

    def makeRecord(self, *args, **kwargs):
        wrapper = LogRecordWrapper(*args)
        wrapper.format()
        return super(AppLogger, self).makeRecord(*wrapper.args)

    def stringify_item(self, key, val):
        bold_value = Styles.BOLD.encode(val)
        return f"{key}: {bold_value}"

    def stringify_items(self, **items):
        string_items = [self.stringify_item(key, val)
            for key, val in items.items()]
        return ' '.join(string_items)

    def items(self, **items):
        self.info(self.stringify_items(**items))

    def _handle_api_exception(self, exc):
        extra = {
            'proxy': exc.proxy,
        }
        if isinstance(exc, exceptions.ClientApiException):
            extra['status_code'] = exc.status_code
            if isinstance(exc, exceptions.InstagramClientApiException):
                extra['result'] = exc.result

        return extra

    def _handle_exception(self, exc, extra=None):
        if isinstance(exc, exceptions.InstagramAttackException):
            msg = exc.message
            if isinstance(exc, exceptions.ApiException):
                new_extra = self._handle_api_exception(exc)
                extra.update(**new_extra)
            return msg, extra
        else:
            msg = str(exc)
            return msg, extra

    def _log(self, level, msg, args, exc_info=None, extra=None):
        extra = extra or {}

        if extra.get('response'):
            extra['status_code'] = extra['response'].status

        if isinstance(msg, Exception):
            msg, extra = self._handle_exception(msg, extra=extra)
        super(AppLogger, self)._log(level, msg, args, exc_info, extra)

    def success(self, message, *args, **kwargs):
        kwargs.setdefault('extra', {})
        kwargs['extra']['isSuccess'] = True

        if kwargs['extra'].get('response'):
            kwargs['extra']['url'] = kwargs['extra']['response'].url

        super(AppLogger, self).info(message, *args, **kwargs)
