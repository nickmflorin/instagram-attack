from __future__ import absolute_import

import aiohttp
import random

from instattack.conf import settings

from instattack.logger import AppLogger


class Handler(object):

    def __init__(self, name):
        self.log = AppLogger(name)


class RequestHandler(Handler):

    _user_agent = None

    def __init__(
        self,
        name,
        method=None,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None
    ):
        super(RequestHandler, self).__init__(name)

        self.method = method

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
        """
        TCPConnector
        -------------
        keepalive_timeout (float) – timeout for connection reusing after
            releasing
        limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
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
