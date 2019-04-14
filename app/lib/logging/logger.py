from __future__ import absolute_import

import aiohttp
import logbook
import inspect

from .formats import LoggingLevels, RecordAttributes, LOGIN_ATTEMPT_FORMAT, TOKEN_TASK_FORMAT
from .formatter import LogItem


__all__ = ('AppLogger', 'log_attempt_context', 'log_token_context', )


# log = logbook.Logger('Main')

# logger_group = logbook.LoggerGroup()
# logger_group.level = logbook.WARNING

# log1 = logbook.Logger('First')
# log2 = logbook.Logger('Second')

# logger_group.add_logger(log1)
# logger_group.add_logger(log2)


def get_exception_status_code(exc):

    if isinstance(exc, aiohttp.ClientError):
        if hasattr(exc, 'status'):
            return exc.status
        elif hasattr(exc, 'status_code'):
            return exc.status_code
        else:
            return None
    else:
        return None


def get_exception_request_method(exc):

    if isinstance(exc, aiohttp.ClientError):
        if hasattr(exc, 'request_info'):
            if exc.request_info.method:
                return exc.request_info.method
    return None


def get_exception_message(exc):
    if isinstance(exc, aiohttp.ClientError):
        message = getattr(exc, 'message', None) or exc.__class__.__name__
        return message

    # Although these are the same for now, we might want to treat our exceptions
    # differently in the future.
    # Maybe return str(exc) if the string length isn't insanely long.
    message = getattr(exc, 'message', None) or str(exc)
    return message


def format_exception_message(exc, level):
    return LogItem(
        LogItem(get_exception_request_method(exc),
            formatter=RecordAttributes.METHOD),
        LogItem(get_exception_message(exc),
            formatter=level),
        LogItem(get_exception_status_code(exc),
            formatter=RecordAttributes.STATUS_CODE)
    )


def format_log_message(msg, level):
    if isinstance(msg, Exception):
        return format_exception_message(msg, level)
    else:
        return RecordAttributes.MESSAGE.format(msg)


def contextual_log(task_format):
    def _contextual_log(func):
        arguments = inspect.getargspec(func).args

        def wrapper(*args, **kwargs):
            handler = logbook.StderrHandler()
            handler.format_string = task_format

            try:
                ind = arguments.index('context')
            except IndexError:
                raise NotImplementedError(
                    "Cannot use decorator on a method that does not take context "
                    "as a positional argument."
                )

            context = args[ind]

            def inject_context(record):
                record.extra['context'] = context

            with logbook.Processor(inject_context).threadbound():
                with handler.threadbound():
                    return func(*args, **kwargs)
        return wrapper
    return _contextual_log


log_token_context = contextual_log(TOKEN_TASK_FORMAT)
log_attempt_context = contextual_log(LOGIN_ATTEMPT_FORMAT)


class AppLogger(logbook.Logger):

    def process_record(self, record):
        logbook.Logger.process_record(self, record)
        level = LoggingLevels[record.level_name]
        record.extra['formatted_level_name'] = level.format(record.level_name)
        record.extra['formatted_message'] = format_log_message(
            record.message, level)
