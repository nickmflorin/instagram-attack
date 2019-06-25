import os

from instattack.ext import get_root
from .app import NAME

USER_DIR = os.path.join(get_root(NAME=NAME), 'users')

INSTAGRAM_USERNAME_FIELD = 'username'
INSTAGRAM_PASSWORD_FIELD = 'password'

# Instagram Response
CHECKPOINT_REQUIRED = "checkpoint_required"
GENERIC_REQUEST_ERROR = 'generic_request_error'
GENERIC_REQUEST_MESSAGE = 'Sorry, there was a problem with your request.'

# TODO: Join File Names in Non Configurable Set Field
PASSWORDS = "passwords"
ALTERATIONS = "alterations"
NUMERICS = "numerics"

USER_FILES = [
    PASSWORDS,
    ALTERATIONS,
    NUMERICS
]

# TODO:
# We might want to make these configurable
USER_SLEEP_ON_SAVE_FAIL = 5
USER_MAX_SAVE_ATTEMPT_TRIES = 4
