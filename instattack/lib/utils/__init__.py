from .asyncio import *  # noqa
from .dbtools import *  # noqa
from .io import *  # noqa
from .itertools import *  # noqa
from .paths import *  # noqa


def filtered_array(*items):
    array = []
    for item in items:
        if isinstance(item, tuple) and len(item) == 2:
            if item[1] is not None:
                array.append(item[0] % item[1])
        elif isinstance(item, tuple) and len(item) == 1:
            if item[0] is not None:
                array.append(item[0])
        else:
            if item is not None:
                array.append(item)
    return array


def is_numeric(value):
    try:
        float(value)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return None
    else:
        try:
            return int(value)
        except ValueError:
            return float(value)
        else:
            if float(value) == int(value):
                return int(value)
            return float(value)
