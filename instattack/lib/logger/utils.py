from datetime import datetime
from plumbum import colors

from .formats import DATE_FORMAT, Format, RecordAttributes


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


def simple_context(record):

    format_context = {}
    format_context['msg'] = record.msg
    format_context['levelname'] = record.levelname
    format_context['name'] = record.name
    format_context['datetime'] = datetime.now().strftime(DATE_FORMAT)
    return format_context


def record_context(record):
    from instattack.lib import (
        get_exception_request_method, get_exception_status_code,
        get_exception_message)

    format_context = {}

    format_context['datetime'] = datetime.now().strftime(DATE_FORMAT)
    format_context['name'] = record.name
    format_context['levelname'] = record.levelname
    format_context['msg'] = record.msg

    if record.is_exception:
        format_context['status_code'] = get_exception_status_code(record.msg)
        format_context['msg'] = get_exception_message(record.msg)
        format_context['method'] = get_exception_request_method(record.msg)

    format_context['other'] = getattr(record, 'other', None)

    format_context['index'] = get_off_record_obj(record, 'index')
    format_context['parent_index'] = get_off_record_obj(record, 'parent_index')
    format_context['password'] = get_off_record_obj(record, 'password')
    format_context['proxy'] = get_off_record_obj(record, 'proxy', tier_key='host')

    # Allow traceback to be overridden.
    format_context['lineno'] = record.lineno
    format_context['filename'] = record.filename

    return format_context


def get_off_record_obj(obj, param, tier_key=None):
    """
    Priorities overridden values explicitly provided in extra, and will
    check record.extra['context'] if the value is not in 'extra'.

    If tier_key is provided and item found is object based, it will try
    to use the tier_key to get a non-object based value.
    """
    if hasattr(obj, param):
        val = getattr(obj, param)
        if val is not None:
            if tier_key:
                return get_off_record_obj(val, tier_key)
            else:
                return val

    if hasattr(obj, 'context'):
        context = obj.context
        return get_off_record_obj(context, param, tier_key=tier_key)

    return None
