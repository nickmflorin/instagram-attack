from tortoise import Tortoise

from instattack import settings
from instattack.logger import AppLogger


log = AppLogger(__name__)


async def database_init():
    await Tortoise.init(config=settings.DB_CONFIG)

    # Generate the schema
    await Tortoise.generate_schemas()
