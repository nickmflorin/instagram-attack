from .base import APP_NAME, DIR_STR, GET_ROOT

USER_SLEEP_ON_SAVE_FAIL = 5
USER_MAX_SAVE_ATTEMPT_TRIES = 4


DB_NAME = APP_NAME
DB_PATH = DIR_STR(GET_ROOT() / f"{APP_NAME}.db")


DB_URL = f'sqlite:///{DB_PATH}'
DB_CONFIG = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.sqlite',
            'credentials': {
                'file_path': DB_PATH,
                'database': APP_NAME,
            }
        },
    },
    'apps': {
        'models': {
            'models': [
                'instattack.src.proxies.models',
                'instattack.src.users.models',
            ],
            'default_connection': 'default',
        }
    }
}
