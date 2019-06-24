from instattack.ext import get_root_file_path
from .app import NAME

DB_NAME = NAME
DB_PATH = get_root_file_path(NAME, ext='db')
DB_URL = f'sqlite:///{DB_PATH}'

DB_CONFIG = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.sqlite',
            'credentials': {
                'file_path': DB_PATH,
                'database': NAME,
            }
        },
    },
    'apps': {
        'models': {
            'models': [
                'instattack.core.models.proxies',
                'instattack.core.models.user',
            ],
            'default_connection': 'default',
        }
    }
}
