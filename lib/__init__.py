from .user import *  # noqa
from .io import *  # noqa
from .paths import *  # noqa
from .pwgen import *  # noqa
from .logger import *  # noqa
from .validation import *  # noqa
from .threading import *  # noqa
from .err_handling import *  # noqa
from .progress import *  # noqa
from .http import *  # noqa


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
