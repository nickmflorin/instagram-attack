from .app import *  # noqa
from .db import *  # noqa
from .http import *  # noqa
from .login import LOGIN  # noqa
from .proxies import PROXIES  # noqa
from .users import *  # noqa

DEBUG = True

LOGGING = {
    'LEVEL': 'INFO',
    'LOG_REQUEST_ERRORS': True,
    'LOG_PROXY_QUEUE': True
}
