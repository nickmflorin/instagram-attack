from instattack import __NAME__
from instattack.ext import get_root_file_path


DB_NAME = __NAME__
DB_PATH = get_root_file_path(__NAME__, ext='db')
DB_URL = f'sqlite:///{DB_PATH}'

DB_CONFIG = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.sqlite',
            'credentials': {
                'file_path': DB_PATH,
                'database': __NAME__,
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
