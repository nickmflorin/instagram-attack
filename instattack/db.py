import os

from tortoise import Tortoise

from instattack.lib import AppLogger, get_root, dir_str
from instattack import settings


SQLITE = 'sqlite:///{DB}'

log = AppLogger(__file__)

path = dir_str(get_root())
db_path = os.path.join(path, f"{settings.APP_NAME}.db")
db_url = SQLITE.format(DB=db_path)


config = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.sqlite',
            'credentials': {
                'file_path': db_path,
                'database': settings.APP_NAME,
            }
        },
    },
    'apps': {
        'models': {
            'models': ['instattack.models'],
            'default_connection': 'default',
        }
    }
}


async def database_init():

    log.start(f'Initializing Database.', extra={'other': db_url})
    await Tortoise.init(config=config)
    log.complete(f'Initialized Database.', extra={'other': db_url})

    # Generate the schema
    await Tortoise.generate_schemas()
    log.complete(f'Generated Database Schemas.')
