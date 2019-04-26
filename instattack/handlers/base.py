from __future__ import absolute_import

import aiohttp
import random

from instattack.conf import settings

from instattack.logger import AppLogger


class Handler(object):

    arguments = ()

    def __init__(self, **kwargs):

        logger_name = kwargs.get('__name__') or self.__class__.__name__
        self.log = AppLogger(logger_name)


class RequestHandler(Handler):

    def __init__(self, method=None, **kwargs):
        super(RequestHandler, self).__init__(**kwargs)

        self.user_agent = random.choice(settings.USER_AGENTS)
        self.method = method

        self.connection_limit = kwargs['connection_limit']
        self.connection_timeout = kwargs['connection_timeout']
        self.connection_force_close = kwargs['connection_force_close']
        self.connection_limit_per_host = kwargs['connection_limit_per_host']
        self.connection_keepalive_timeout = kwargs['connection_keepalive_timeout']

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
            force_close=self.connection_force_close,
            limit=self.connection_limit,
            limit_per_host=self.connection_limit_per_host,
            keepalive_timeout=self.connection_keepalive_timeout,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(total=self.connection_timeout)
