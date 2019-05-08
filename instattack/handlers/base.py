import aiohttp
import random

from instattack import settings
from .control import Control


class Handler(Control):

    def __init__(self, **kwargs):
        self.engage(**kwargs)


class RequestHandler(Handler):

    _user_agent = None

    def __init__(
        self,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None,
        **kwargs,
    ):
        super(RequestHandler, self).__init__(**kwargs)

        self._connection_limit = connection_limit
        self._session_timeout = session_timeout
        self._connection_force_close = connection_force_close
        self._connection_limit_per_host = connection_limit_per_host
        self._connection_keepalive_timeout = connection_keepalive_timeout

    def _notify_request(self, context, retry=1):
        message = f'Sending {self.__method__} Request'
        if retry != 1:
            message = f'Sending {self.__method__} Request, Retry {retry}'
        self.log.debug(message, extra={'context': context})

    @property
    def user_agent(self):
        if not self._user_agent:
            self._user_agent = random.choice(settings.USER_AGENTS)
        return self._user_agent

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def _connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=self._connection_force_close,
            limit=self._connection_limit,
            limit_per_host=self._connection_limit_per_host,
            keepalive_timeout=self._connection_keepalive_timeout,
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self._session_timeout
        )