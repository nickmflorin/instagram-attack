from tortoise import Tortoise

from instattack import settings
from instattack.logger import AppLogger


log = AppLogger(__name__)


async def database_init():

    log.start(f'Initializing Database.', extra={'other': settings.DB_URL})
    await Tortoise.init(config=settings.DB_CONFIG)
    log.complete(f'Initialized Database.', extra={'other': settings.DB_URL})

    # Generate the schema
    await Tortoise.generate_schemas()
    log.complete(f'Generated Database Schemas.')
