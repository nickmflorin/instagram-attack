import os

from tortoise import Tortoise

from lib import AppLogger
from instattack import settings


SQLITE = 'sqlite:///{DB}'

log = AppLogger(__file__)


async def database_init(dbname=None):
    dbname = dbname or settings.APP_NAME

    db_path = os.path.join(os.getcwd(), f"{dbname}.db")
    db_url = SQLITE.format(DB=db_path)
    await Tortoise.init(
        db_url=db_url,
        modules={'models': ['instattack.models']}
    )
    # Generate the schema
    await Tortoise.generate_schemas()
