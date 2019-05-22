import inspect
import re

from .exceptions import InvalidRecordCallable


def ensure_list(value):
    if not isinstance(value, list):
        if isinstance(value, tuple):
            return list(value)
        return [value]
    return value


def escape_ansi_string(value):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', value)


def humanize_list(value, callback=str, conjunction='and', oxford_comma=True):
    """
    Turns an interable list into a human readable string.
    >>> list = ['First', 'Second', 'Third', 'fourth']
    >>> humanize_list(list)
    u'First, Second, Third, and fourth'
    >>> humanize_list(list, conjunction='or')
    u'First, Second, Third, or fourth'
    """

    num = len(value)
    if num == 0:
        return ""
    elif num == 1:
        return callback(value[0])
    s = u", ".join(map(callback, value[:num - 1]))
    if len(value) >= 3 and oxford_comma is True:
        s += ","
    return "%s %s %s" % (s, conjunction, callback(value[num - 1]))


def get_obj_attribute(obj, param):
    """
    Given an object, returns the parameter for that object if it exists.  The
    parameter can be nested, by including "." to separate the nesting of objects.

    For example, get_obj_attribute(test_obj, 'fruits.apple.name') would get
    the 'fruits' object off of `test_obj`, then the 'apple' object and then
    the 'name' attribute on the 'apple' object.
    """
    if "." in param:
        parts = param.split(".")
        if len(parts) > 1:
            if hasattr(obj, parts[0]):
                nested_obj = getattr(obj, parts[0])
                return get_obj_attribute(nested_obj, '.'.join(parts[1:]))
            else:
                return None
        else:
            if hasattr(obj, parts[0]):
                return getattr(obj, parts[0])
    else:
        if hasattr(obj, param):
            return getattr(obj, param)
        return None


def get_record_attribute(params, record):

    def sort_priority(param):
        return param.count(".")

    # TODO: Need to catch more singletons here.
    params = ensure_list(params)
    params = ["%s" % param for param in params]
    params = sorted(params, key=sort_priority)

    # Here, each param can be something like "context.index", or "index"
    # Higher priority is given to less deeply nested versions.
    for param in params:
        value = get_obj_attribute(record, param)
        if value is not None:
            return value
    return None


def is_record_callable(value):
    if callable(value):
        argspec = inspect.getargspec(value)
        if len(argspec.args) == 1 and argspec.args[0] == 'record':
            return True


def get_formatter_value(value, record):
    if callable(value):
        if is_record_callable(value):
            return value(record)
        else:
            return value
    return value


def get_log_value(value, record):
    """
    TODO
    ----
    Need to clean this portion up a bit.
    """
    if callable(value):
        if is_record_callable(value):
            return value(record)
        else:
            raise InvalidRecordCallable(value)

    attr = get_record_attribute(value, record)
    if attr:
        return attr

    # Cannot return constant strings otherwise things that are meant for params
    # on record but not present on record will return as strings.
    return None
