from __future__ import absolute_import

import contextlib
import logbook
import inspect
import sys

from app.lib.utils import (
    get_exception_request_method, get_exception_message, get_exception_status_code)

from .formats import (LoggingLevels, RecordAttributes, APP_FORMAT,
    LOGIN_TASK_FORMAT, LOGIN_ATTEMPT_FORMAT, TOKEN_TASK_FORMAT)
from .formatter import LogItem


__all__ = ('AppLogger', 'create_handlers', 'contextual_log', )


def format_exception_message(exc, level):
    items = []

    method = get_exception_request_method(exc)
    if method:
        items.append(
            LogItem(method, formatter=RecordAttributes.METHOD),
        )

    message = get_exception_message(exc)
    items.append(LogItem(message, formatter=level))

    status_code = get_exception_status_code(exc)
    if status_code:
        items.append(
            LogItem(status_code, formatter=RecordAttributes.STATUS_CODE),
        )
    return LogItem(*tuple(items))


def format_log_message(msg, level):
    if isinstance(msg, Exception):
        return format_exception_message(msg, level)
    else:
        return RecordAttributes.MESSAGE.format(msg)


# This currently doesn't seem to be working...
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
def create_handlers(config):

    def filter_token_context(r, h):
        return r.extra['context'] and r.extra['context'].context_id == 'token'

    def filter_login_context(r, h):
        return r.extra['context'] and r.extra['context'].context_id == 'login'

    def filter_attempt_context(r, h):
        return r.extra['context'] and r.extra['context'].context_id == 'attempt'

    base_handler = logbook.StreamHandler(sys.stdout, level=config.level, bubble=True)
    base_handler.format_string = APP_FORMAT

    token_handler = logbook.StreamHandler(
        sys.stdout,
        level=config.level,
        filter=filter_token_context
    )

    token_handler.format_string = TOKEN_TASK_FORMAT

    login_handler = logbook.StreamHandler(
        sys.stdout,
        level=config.level,
        filter=filter_login_context
    )

    login_handler.format_string = LOGIN_TASK_FORMAT

    attempt_handler = logbook.StreamHandler(
        sys.stdout,
        level=config.level,
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
