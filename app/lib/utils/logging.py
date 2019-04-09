from __future__ import absolute_import

import requests
import aiohttp

from app.lib import exceptions

from .formatting import LoggingLevels, RecordAttributes, Styles
from .misc import array_string


__all__ = ('RecordFormatter', )


def get_exception_status_code(exc, formatted=False):

    if isinstance(exc, requests.exceptions.RequestException):
        if exc.response and exc.response.status_code:
            if formatted:
                return RecordAttributes.STATUS_CODE.format(exc.response.status_code)
            return exc.response.status_code
    elif isinstance(exc, aiohttp.ClientError):
        if formatted:
            return RecordAttributes.STATUS_CODE.format(exc.status)
        return exc.status
    else:
        return None


def get_exception_request_method(exc, formatted=False):
    if isinstance(exc, requests.exceptions.RequestException):
        if exc.request and exc.request.method:
            if formatted:
                return RecordAttributes.METHOD.format(exc.request.method)
            return exc.request.method
    elif isinstance(exc, aiohttp.ClientError):
        if exc.request_info.method:
            if formatted:
                return RecordAttributes.METHOD.format(exc.request_info.method)
            return exc.request_info.method
    return None


def get_exception_message(exc, level, formatted=False):
    if isinstance(level, str):
        level = LoggingLevels[level]

    if (isinstance(exc, requests.exceptions.RequestException) or
            isinstance(exc, aiohttp.ClientError)):
        message = getattr(exc, 'message', None) or exc.__class__.__name__
        if formatted:
            return level.format_message(message)
        return message

    # Although these are the same for now, we might want to treat our exceptions
    # differently in the future.
    # Maybe return str(exc) if the string length isn't insanely long.
    message = getattr(exc, 'message', None) or str(exc)
    if formatted:
        return level.format_message(message)
    return message


def format_exception_message(exc, level):
    return array_string(
        get_exception_request_method(exc, formatted=True),
        get_exception_message(exc, level, formatted=True),
        get_exception_status_code(exc, formatted=True)
    )


def format_log_message(msg, level):
    if isinstance(msg, Exception):
        return format_exception_message(msg, level)
    else:
        msg = level.format_message(msg)
        return RecordAttributes.MESSAGE.format(msg)


class RecordFormatter(object):

    def __init__(self, record):
        self.record = record
        self.level = LoggingLevels[self.levelname]

    def __getattr__(self, key):
        if key == 'levelname' and self.isSuccess:
            return 'SUCCESS'
        return getattr(self.record, key, None)

    @property
    def _msg(self):
        return format_log_message(self.msg, self.level)

    @property
    def _password(self):
        if self.password:
            return RecordAttributes.PASSWORD.format(self.password)

    @property
    def _task(self):
        if self.task:
            if isinstance(self.task, str):
                return RecordAttributes.TASK.format(self.task)
            elif hasattr(self.task, 'name'):
                return RecordAttributes.TASK.format(self.task.name)
            else:
                raise exceptions.FatalException('Invalid task supplied to logger.')

    @property
    def _traceback(self):
        # See note in AppLogger.makeRecord()
        # If line_no and file_name not explicitly provided, or we are not in
        # DEBUG, CRITICAL or ERROR levels, don't include in message.
        if (
            not (self.line_no and self.file_name) and
                self.levelname not in ('ERROR', 'CRITICAL', 'DEBUG')
        ):
            return None

        lineno = self.line_no or self.lineno
        filename = self.file_name or self.filename
        if lineno and filename:
            return f"({filename}, {Styles.BOLD.format(lineno)})"

    @property
    def _proxy(self):
        if self.proxy:
            if isinstance(self.proxy, str):
                return RecordAttributes.PROXY.format(self.proxy)
            else:
                return RecordAttributes.PROXY.format(
                    f"{self.proxy.host}:{self.proxy.port}"
                )

    @property
    def _threadName(self):
        if self.threadName:
            return RecordAttributes.THREADNAME.format(self.threadName)

    @property
    def _name(self):
        if self.name:
            return RecordAttributes.NAME.format(self.name)

    @property
    def _token(self):
        if self.token:
            return RecordAttributes.TOKEN.format(self.token)

    @property
    def _levelname(self):
        return LoggingLevels[self.levelname].format(self.levelname)

    @property
    def _status_code(self):
        if get_exception_status_code(self.msg):
            return None

        if self.response and not self.status_code:
            status_code = (
                getattr(self.response, 'status_code', None) or
                getattr(self.response, 'status', None)
            )
            return RecordAttributes.STATUS_CODE.format(status_code)
        elif self.status_code:
            return RecordAttributes.STATUS_CODE.format(self.status_code)