from datetime import datetime
from plumbum import colors

from .formats import RecordAttributes, Format, DATE_FORMAT


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
    return datetime.now().strftime(DATE_FORMAT)


def get_level_formatter(record):
    if getattr(record, 'level_format', None):
        return record.level_format
    elif getattr(record, 'color', None):
        return Format(record.color, colors.bold)
    else:
        return record.level


def get_message_formatter(record):
    if getattr(record, 'highlight', None):
        return RecordAttributes.SPECIAL_MESSAGE
    elif getattr(record, 'level_format', None):
        return record.level_format.message_formatter
    elif getattr(record, 'color', None):
        return Format(record.color)
    else:
        return record.level.message_formatter
