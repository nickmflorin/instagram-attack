import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from instattack import settings
from instattack.lib.logger import AppLogger
from instattack.lib.utils import validate_method


SQLITE = 'sqlite'


log = AppLogger(__file__)
Base = declarative_base()


class Database:
    # http://docs.sqlalchemy.org/en/latest/core/engines.html
    DB_ENGINE = {
        SQLITE: 'sqlite:///{DB}'
    }

    # Main DB Connection Ref Obj
    engine = None

    def __init__(self, dbtype, username='', password='', dbname=''):

        engine_url = self.DB_ENGINE.get(dbtype.lower())
        if engine_url is None:
            raise ValueError(f"Invalid dbtype {dbtype}.")

        db_path = os.path.join(os.getcwd(), f"{dbname}.db")

        self._session = None
        self.engine_url = engine_url.format(DB=db_path)
        self.engine = create_engine(self.engine_url)
        self.DBSession = sessionmaker(bind=self.engine)

        # Bind the engine to the metadata of the Base class so that the
        # declaratives can be accessed through a DBSession instance
        Base.metadata.bind = self.engine

    @property
    def session(self):
        if not self._session:
            self._session = self.DBSession()
        return self._session

    def create_tables(self):
        Base.metadata.create_all(self.engine)


db = Database('sqlite', dbname=settings.DB_NAME)


async def stream_proxies(method, limit=None):
    from instattack.models.proxies import Proxy, ProxyError  # noqa

    method = validate_method(method)

    found = []
    for proxy in db.session.query(Proxy).filter(method == method):
        if proxy.type_id not in [p.type_id for p in found]:
            yield proxy
            found.append(proxy)
        else:
            log.warning(f'Found Duplicate Proxy', extra={'proxy': proxy})
