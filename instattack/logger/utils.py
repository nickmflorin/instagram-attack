from datetime import datetime
from enum import Enum
from plumbum import colors


class Format(object):
    def __init__(self, *args, wrapper=None, format_with_wrapper=False):
        self.colors = args
        self.wrapper = wrapper
        self.format_with_wrapper = format_with_wrapper

    def __call__(self, text):

        if self.wrapper and self.format_with_wrapper:
            text = self.wrapper % text

        c = colors.do_nothing
        for i in range(len(self.colors)):
            c = c & self.colors[i]

        # Apply wrapper after styling so we don't style the wrapper.
        text = (c | text)

        if self.wrapper and not self.format_with_wrapper:
            text = self.wrapper % text
        return text

    def without_text_decoration(self):
        undecorated = [c for c in self.colors
            if c not in [colors.underline, colors.bold]]
        return Format(
            *undecorated,
            wrapper=self.wrapper,
            format_with_wrapper=self.format_with_wrapper
        )


class FormattedEnum(Enum):

    def __init__(self, format):
        if isinstance(format, dict):
            self.format = format['base']
            self.formats = format
        else:
            self.format = format
            self.formats = {'base': format}

    def __call__(self, text):
        return self.format(text)


def get_record_message(record):
    from instattack.lib import get_exception_message

    if isinstance(record.msg, Exception):
        return get_exception_message(record.msg)
    return record.msg


def get_record_status_code(record):
    from instattack.lib import get_exception_status_code

    status_code = None
    if isinstance(record.msg, Exception):
        status_code = get_exception_status_code(record.msg)
    if not status_code:
        if hasattr(record, 'response') and hasattr(record.response, 'status'):
            status_code = record.response.status
    return status_code


def get_record_response_reason(record):
    if hasattr(record, 'response') and hasattr(record.response, 'reason'):
        return record.response.reason


def get_record_request_method(record):
    from instattack.lib import get_exception_request_method

    method = None
    if isinstance(record.msg, Exception):
        method = get_exception_request_method(record.msg)
    if not method:
        if hasattr(record, 'response') and hasattr(record.response, 'method'):
            method = record.response.method
    return method


def get_record_time(record):
    from .constants import DATE_FORMAT
    return datetime.now().strftime(DATE_FORMAT)


def get_level_formatter(record):
    if getattr(record, 'color', None):
        return Format(record.color, colors.bold)
    else:
        return record.level.format


def get_message_formatter(record):
    from .constants import RecordAttributes
    if getattr(record, 'highlight', None):
        return RecordAttributes.SPECIAL_MESSAGE
    elif getattr(record, 'level_format', None):
        return record.level_format.message_formatter
    elif getattr(record, 'color', None):
        return Format(record.color)
    else:
        return record.level.message_formatter
