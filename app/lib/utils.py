from __future__ import absolute_import

import asyncio
import aiohttp

from argparse import ArgumentTypeError
from collections import Iterable
import traceback


async def cancel_remaining_tasks(futures):
    tasks = [task for task in futures if task is not
         asyncio.tasks.Task.current_task()]
    list(map(lambda task: task.cancel(), tasks))
    await asyncio.gather(*tasks, return_exceptions=True)


def validate_int(n):
    try:
        return int(n)
    except TypeError:
        raise ArgumentTypeError("Argument must be a valid integer")


def validate_log_level(val):
    levels = [
        'INFO',
        'DEBUG',
        'WARNING',
        'SUCCESS',
        'CRITICAL',
    ]

    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in levels:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


def ensure_iterable(arg):
    if isinstance(arg, str):
        return [arg]
    elif not isinstance(arg, Iterable):
        return [arg]
    return arg


def array(*values):
    return [val for val in values if val is not None]


def array_string(*values, separator=" "):
    values = array(*values)
    return separator.join(values)


def get_token_from_cookies(cookies):
    # aiohttp ClientResponse cookies have .value attribute.
    cookie = cookies.get('csrftoken')
    if cookie:
        return cookie.value


def get_cookies_from_response(response):
    return response.cookies


def get_token_from_response(response):
    cookies = get_cookies_from_response(response)
    if cookies:
        return get_token_from_cookies(cookies)


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
