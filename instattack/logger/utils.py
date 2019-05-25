from datetime import datetime
from plumbum import LocalPath, colors
import os

from .constants import DATE_FORMAT, RecordAttributes
from .format import Format


def is_log_file(path):
    pt = LocalPath(path)
    if 'logger' in pt.parts:
        module_index = pt.parts.index('logger')
        parts = pt.parts[:module_index + 1]
        full_path = os.path.join('/', *parts)
        if path.startswith(full_path):
            return True
    return False


def get_record_message(record):
    if isinstance(record.msg, Exception):
        return get_exception_message(record.msg)
    return record.msg


def get_exception_message(exc):

    error_message = exc.__class__.__name__

    message = getattr(exc, 'message', None) or str(exc)
    if message != "" and message is not None:
        error_message = f"{exc.__class__.__name__}: {message}"
    else:
        if hasattr(exc, 'strerror'):
            error_message = f"{exc.__class__.__name__}: {exc.strerror}"

    err_no = get_exception_err_no(exc)
    if err_no:
        error_message += (f' (ErrNo: {err_no})')

    return error_message


def get_exception_err_no(exc):
    if hasattr(exc, 'errno'):
        return exc.errno
    return None


def get_exception_status_code(exc):

    if hasattr(exc, 'status'):
        return exc.status
    elif hasattr(exc, 'status_code'):
        return exc.status_code
    else:
        return None


def get_exception_request_method(exc):

    if hasattr(exc, 'request_info'):
        if exc.request_info.method:
            return exc.request_info.method
    return None


def get_record_status_code(record):

    status_code = get_exception_status_code(record.msg)
    if not status_code:
        if hasattr(record, 'response') and hasattr(record.response, 'status'):
            status_code = record.response.status
    return status_code


def get_record_response_reason(record):
    if hasattr(record, 'response') and hasattr(record.response, 'reason'):
        return record.response.reason


def get_record_request_method(record):

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
