# from .app import *  # noqa
# from .db import *  # noqa
# from .http import *  # noqa
from .login import LOGIN  # noqa
# from .proxies import PROXIES  # noqa
# from .users import *  # noqa

from instattack.config import fields

DEBUG = True

# Make Non Configurable for Now
LOGGING = fields.SetField(
    LEVEL='INFO',
    LOG_REQUEST_ERRORS=True,
    LOG_PROXY_QUEUE=True,
    DEFAULT_MODE='termx',
    configurable=False,
)
