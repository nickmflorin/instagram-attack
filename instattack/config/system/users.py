import os

from instattack.ext import get_root
from .app import NAME

USER_DIR = os.path.join(get_root(NAME=NAME), 'users')

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
