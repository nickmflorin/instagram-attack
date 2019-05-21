import re


def escape_ansi_string(value):
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', value)


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
