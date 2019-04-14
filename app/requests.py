from __future__ import absolute_import

import asyncio
import aiohttp

import random

from app import settings

"""
TODO
-----
Introduce timeout here if we cannot retrieve the token - if there is a connection
error we might not retrieve a token for any of the proxies.

We might want to try to refresh proxies after they are retrieved from
the queue if the request is successful.

NOTES
------
We can use the following url to make sure that requests are using the proxy
correctly:
future = session.get('https://api.ipify.org?format=json')
"""


class HandlerSettings(object):

    # TODO
    # ATTEMPT_LIMIT = settings.REQUESTS.ATTEMPT_LIMIT.login

    @property
    def FIRST_ATTEMPT_LIMIT(self):
        return settings.REQUESTS.value(
            'FIRST_ATTEMPT_LIMIT', self.__handlername__)

    @property
    def CONNECTOR_KEEP_ALIVE_TIMEOUT(self):
        return settings.REQUESTS.value(
            'CONNECTOR_KEEP_ALIVE_TIMEOUT', self.__handlername__)

    @property
    def FETCH_TIME(self):
        return settings.REQUESTS.value(
            'FETCH_TIME', self.__handlername__)

    @property
    def MAX_REQUEST_RETRY_LIMIT(self):
        return settings.REQUESTS.value(
            'MAX_REQUEST_RETRY_LIMIT', self.__handlername__)


class request_handler(HandlerSettings):

    def __init__(self, config, global_stop_event, proxy_handler):
        self.config = config
        self.global_stop_event = global_stop_event
        self.user_agent = random.choice(settings.USER_AGENTS)
        self.stop_event = asyncio.Event()
        self.proxy_handler = proxy_handler

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def connector(self):
        """
        TCPConnector
        -------------
        keepalive_timeout (float) – timeout for connection reusing aftet
            releasing
        limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
        return aiohttp.TCPConnector(
            ssl=False,
            keepalive_timeout=self.CONNECTOR_KEEP_ALIVE_TIMEOUT,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=self.FETCH_TIME
        )

    def log_request(self, context, log, retry=1, method="GET"):
        if retry == 1:
            log.info(
                f'Sending {method.upper()} Request',
                extra=context.log_context(backstep=3),
            )
        else:
            log.info(
                f'Sending {method.upper()} Request, Attempt {retry}',
                extra=context.log_context(backstep=3),
            )

    def log_post_request(self, context, log, retry=1):
        self.log_request(context, log, retry=1, method='POST')

    def log_get_request(self, context, log, retry=1):
        self.log_request(context, log, retry=1, method='GET')
