from datetime import datetime


def record_context(record):
    from instattack.lib import (
        get_exception_request_method, get_exception_status_code,
        get_exception_message)

    from instattack.lib.logger.formats import DATE_FORMAT

    format_context = {}

    format_context['datetime'] = datetime.now().strftime(DATE_FORMAT)
    format_context['name'] = record.name
    format_context['levelname'] = record.levelname
    format_context['message'] = record.msg

    if record.is_exception:
        format_context['status_code'] = get_exception_status_code(record.msg)
        format_context['message'] = get_exception_message(record.msg)
        format_context['method'] = get_exception_request_method(record.msg)

    format_context['other'] = getattr(record, 'other', None)

    format_context['index'] = contextual_retrieval(record, 'index')
    format_context['parent_index'] = contextual_retrieval(record, 'parent_index')
    format_context['password'] = contextual_retrieval(record, 'password')
    format_context['proxy'] = contextual_retrieval(record, 'proxy', tier_key='host')

    # Allow traceback to be overridden.
    format_context['lineno'] = record.lineno
    format_context['filename'] = record.filename

    return format_context


def contextual_retrieval(record, param, tier_key=None):
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

    if hasattr(record, param):
        return getattr(record, param)
    else:
        if hasattr(record, 'context'):
            ctx = record.context
            if hasattr(ctx, param):
                value = getattr(ctx, param)
                return flexible_obj_get(value)
    return None


def optional_indent(no_indent=False):
    def _opt_indent(val):
        if not no_indent:
            return val
        return 0
    return _opt_indent
