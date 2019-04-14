from __future__ import absolute_import

import aiohttp
import contextlib
import logbook
import inspect
import sys

from .formats import (LoggingLevels, RecordAttributes, APP_FORMAT,
    LOGIN_TASK_FORMAT, LOGIN_ATTEMPT_FORMAT, TOKEN_TASK_FORMAT)
from .formatter import LogItem


__all__ = ('AppLogger', 'create_handlers', 'contextual_log', )


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
    if isinstance(exc, OSError):
        if hasattr(exc, 'strerror'):
            return exc.strerror

    message = getattr(exc, 'message', None) or str(exc)
    if message == "":
        return exc.__class__.__name__
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


def contextual_log(func):

    arguments = inspect.getargspec(func).args
    try:
        context_index = arguments.index('context')
    except IndexError:
        raise NotImplementedError(
            "Cannot use decorator on a method that does not take context "
            "as a positional argument."
        )

    def wrapper(*args, **kwargs):
        context = args[context_index]

        def inject_context(record):
            record.extra['context'] = context

        with logbook.Processor(inject_context).threadbound():
            return func(*args, **kwargs)

    return wrapper


@contextlib.contextmanager
def create_handlers(arguments):

    def filter_token_context(r, h):
        return r.extra['context'] and r.extra['context'].context_id == 'token'

    def filter_login_context(r, h):
        return r.extra['context'] and r.extra['context'].context_id == 'login'

    def filter_attempt_context(r, h):
        return r.extra['context'] and r.extra['context'].context_id == 'attempt'

    base_handler = logbook.StreamHandler(sys.stdout, level=arguments.level, bubble=True)
    base_handler.format_string = APP_FORMAT

    token_handler = logbook.StreamHandler(
        sys.stdout,
        level=arguments.level,
        filter=filter_token_context
    )

    token_handler.format_string = TOKEN_TASK_FORMAT

    login_handler = logbook.StreamHandler(
        sys.stdout,
        level=arguments.level,
        filter=filter_login_context
    )

    login_handler.format_string = LOGIN_TASK_FORMAT

    attempt_handler = logbook.StreamHandler(
        sys.stdout,
        level=arguments.level,
        filter=filter_attempt_context
    )

    attempt_handler.format_string = LOGIN_ATTEMPT_FORMAT

    with base_handler, token_handler, login_handler, attempt_handler:
        yield


class AppLogger(logbook.Logger):

    def process_record(self, record):
        logbook.Logger.process_record(self, record)
        level = LoggingLevels[record.level_name]

        record.extra['formatted_level_name'] = level.format(record.level_name)
        record.extra['formatted_message'] = format_log_message(
            record.message, level)
