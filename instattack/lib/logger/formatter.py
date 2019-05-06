from instattack.lib.utils import (get_exception_request_method,
    get_exception_message, get_exception_status_code)

from .utils import LogItem, LogItemLine
from .formats import RecordAttributes, LoggingLevels, FORMAT_STRING


def format_exception_message(exc, level):
    FORMAT_EXCEPTION_MESSAGE = LogItemLine(
        LogItem('method', formatter=RecordAttributes.METHOD),
        LogItem('message', formatter=level),
        LogItem('status_code', formatter=RecordAttributes.STATUS_CODE),
    )

    message = get_exception_message(exc)

    return FORMAT_EXCEPTION_MESSAGE.format(
        status_code=get_exception_status_code(exc),
        message=message,
        method=get_exception_request_method(exc)
    )


def format_log_message(msg, level):
    if isinstance(msg, Exception):
        return format_exception_message(msg, level)
    else:
        return LogItem('message', formatter=level).format(message=msg)


def app_formatter(record, handler):

    def flexible_retrieval(param, tier_key=None):
        """
        Priorities overridden values explicitly provided in extra, and will
        check record.extra['context'] if the value is not in 'extra'.

        If tier_key is provided and item found is object based, it will try
        to use the tier_key to get a non-object based value.
        """
        def flexible_obj_get(value):
            if hasattr(value, '__dict__') and tier_key:
                return getattr(value, tier_key)
            return value

        if record.extra.get(param):
            return flexible_obj_get(record.extra[param])
        else:
            if hasattr(record, param):
                return getattr(record, param)
            else:
                if record.extra.get('context'):
                    ctx = record.extra['context']
                    if hasattr(ctx, param):
                        value = getattr(ctx, param)
                        return flexible_obj_get(value)
            return None

    format_context = {}

    level = LoggingLevels[record.level_name]
    format_context['channel'] = record.channel
    format_context['formatted_level_name'] = level.format(record.level_name)
    format_context['formatted_message'] = format_log_message(record.message, level)

    # TODO: Might want to format 'other' message differently.
    format_context['other_message'] = flexible_retrieval('other')

    format_context['index'] = flexible_retrieval('index')
    format_context['parent_index'] = flexible_retrieval('parent_index')
    format_context['password'] = flexible_retrieval('password')

    format_context['proxy'] = flexible_retrieval('proxy', tier_key='host')

    # Allow traceback to be overridden.
    format_context['lineno'] = flexible_retrieval('lineno')
    format_context['filename'] = flexible_retrieval('filename')

    return FORMAT_STRING(no_indent=record.extra.get('no_indent', False)).format(**format_context)
