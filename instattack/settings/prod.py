# from .app import *  # noqa
# from .db import *  # noqa
# from .http import *  # noqa
# from .login import LOGIN  # noqa
# from .proxies import PROXIES  # noqa
# from .users import *  # noqa

NAME = 'instattack'
FORMAL_NAME = NAME.title()
VERSION = (0, 0, 2, 'alpha', 0)

DEBUG = True

LOGGING = {
    'LEVEL': 'ERROR',
    'LOG_REQUEST_ERRORS': False,
    'LOG_PROXY_QUEUE': False
}
