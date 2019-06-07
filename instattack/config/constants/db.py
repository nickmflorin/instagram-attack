from .base import APP_NAME, DIR_STR, GET_ROOT


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
                'instattack.app.models.proxies',
                'instattack.app.models.user',
            ],
            'default_connection': 'default',
        }
    }
}
