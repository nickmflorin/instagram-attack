from .coro import *  # noqa
from .decoratives import *  # noqa
from .decorators import *  # noqa
from .err_handling import *  # noqa
from .io import *  # noqa
from .progress import *  # noqa


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
