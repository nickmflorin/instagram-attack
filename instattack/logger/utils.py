from datetime import datetime
from plumbum import colors

from instattack.lib import (get_exception_message, get_exception_status_code,
    get_exception_request_method, get_obj_attribute)

from .constants import DATE_FORMAT, RecordAttributes
from .format import Format


def get_record_attribute(record, params=None, getter=None):

    def sort_priority(param):
        return param.count(".")

    if params:
        if isinstance(params, str):
            params = [params]
        params = sorted(params, key=sort_priority)

        # Here, each param can be something like "context.index", or "index"
        # Higher priority is given to less deeply nested versions.
        for param in params:
            value = get_obj_attribute(record, param)
            if value is not None:
                return value
    else:
        return getter(record)


def get_record_message(record):

    if isinstance(record.msg, Exception):
        return get_exception_message(record.msg)
    return record.msg


def get_record_status_code(record):

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
    if getattr(record, 'color', None):
        return Format(record.color, colors.bold)
    else:
        return record.level.format


def get_message_formatter(record):

    if getattr(record, 'highlight', None):
        return RecordAttributes.SPECIAL_MESSAGE
    elif getattr(record, 'level_format', None):
        return record.level_format.message_formatter
    elif getattr(record, 'color', None):
        return Format(record.color)
    else:
        return record.level.message_formatter
