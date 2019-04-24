from __future__ import absolute_import

import aiohttp
import random

from instattack.conf import settings

from instattack.logger import AppLogger


class Handler(object):

    def __init__(self, user, **kwargs):
        self.user = user

        logger_name = kwargs.get('__name__') or self.__class__.__name__
        self.log = AppLogger(logger_name)


class RequestHandler(Handler):

    def __init__(self, user, method=None, fetch_time=None, connection_limit=None,
            connector_timeout=None, **kwargs):
        super(RequestHandler, self).__init__(user, **kwargs)

        self.user_agent = random.choice(settings.USER_AGENTS)

        self.method = method
        self.fetch_time = fetch_time
        self.connection_limit = connection_limit
        self.connector_timeout = connector_timeout

    def _notify_request(self, context, retry=1):
        message = f'Sending {self.__method__} Request'
        if retry != 1:
            message = f'Sending {self.__method__} Request, Retry {retry}'
        self.log.debug(message, extra={'context': context})

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def connector(self):
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
            limit=self.connection_limit,
            keepalive_timeout=self.connector_timeout,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(total=self.fetch_time)
