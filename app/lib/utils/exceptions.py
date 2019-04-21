from __future__ import absolute_import

import traceback
import sys

import aiohttp

from app.lib import exceptions


def handle_global_exception(exc, exc_info=None):

    ex_type, ex, tb = exc_info
    log = tb.tb_frame.f_globals.get('log')
    if not log:
        log = tb.tb_frame.f_locals.get('log')

    # Array of lines for the stack trace - might be useful later.
    # trace = traceback.format_exception(ex_type, ex, tb, limit=3)

    log.exception(exc, extra={
        'lineno': tb.tb_frame.f_lineno,
        'filename': tb.tb_frame.f_code.co_filename,
    })
    # else:
    #     log.critical("Uncaught Exception")
    #     # This can raise a "no exception occured" error with logbook if the
    #     # exception is something like a TimeoutError where there is no message.
    #     log.exception(exc)
    #     # if callback:
    #     #     callback_args = callback_args or ()
    #     #     return callback_args(*callback_args)


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
    if message == "" or message is None:
        return exc.__class__.__name__
    return message


def get_frame(steps):
    stack = traceback.extract_stack()
    steps += 1
    stack[-(steps)]


def get_stack(tb=None):
    if tb:
        stack = traceback.extract_tb(tb)
    else:
        stack = traceback.extract_stack()
    stack = [st for st in stack if not st.filename.startswith('/Library/Frameworks/')]
    return stack


def get_traceback_info(tb=None, stack=None, backstep=1):
    if not stack:
        backstep += 1
        stack = get_stack(tb=tb)

    frame = stack[-(backstep)]

    return {
        'lineno': frame.lineno,
        'filename': frame.filename,
    }


def log_tb_context(tb=None, stack=None, backstep=1):
    """
    Providing to the log method as the value of `extra`.  We cannot get
    the actual stack trace lineno and filename to be overridden on the
    logRecord (see notes in AppLogger.makeRecord()) - so we provide custom
    values that will override if present.
    """
    backstep += 1
    return get_traceback_info(tb=tb, stack=stack, backstep=backstep)
