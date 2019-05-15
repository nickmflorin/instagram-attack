import asyncio
import aiohttp
import random

from instattack import settings

from .mixins import HandlerMixin, MethodHandlerMixin


class BaseHandler(object):

    def __init__(self, **kwargs):
        self.engage(**kwargs)


class Handler(BaseHandler, HandlerMixin):
    pass


class MethodHandler(BaseHandler, MethodHandlerMixin):
    pass


class RequestHandler(MethodHandler):

    _user_agent = None

    def __init__(self, config, proxy_handler, **kwargs):
        super(RequestHandler, self).__init__(**kwargs)
        self.proxy_handler = proxy_handler

        if self.__method__ is None:
            raise RuntimeError('Method should not be null.')

        config = config.for_method(self.__method__)
        self.limit = config['connection']['limit']
        self.timeout = config['connection']['timeout']
        self.force_close = config['connection']['force_close']
        self.limit_per_host = config['connection']['limit_per_host']

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
            force_close=self.force_close,
            limit=self.limit,
            limit_per_host=self.limit_per_host,
            keepalive_timeout=0,
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self.timeout
        )

    def maintain_proxy(self, proxy):
        """
        >>> Not sure if using these callbacks versus just creating the tasks immediately
        >>> in the async func makes a huge difference, but we'll keep for now.
        """
        proxy.update_time()
        asyncio.create_task(self.proxy_handler.pool.put(proxy))

    def add_proxy_success(self, proxy):
        proxy.was_success()
        asyncio.create_task(self.proxy_handler.pool.put(proxy))

    def add_proxy_error(self, proxy, e):
        """
        Since errors are stored as foreign keys and not on the proxy, we
        have to save them.  That is a lot of database transactions that
        slow down the process of finding the token.

        We also don't have to worry about those proxies being reused when
        finding the token, since the token is found relatively quickly.

        >>> Not sure if using these callbacks versus just creating the tasks immediately
        >>> in the async func makes a huge difference, but we'll keep for now.
        """
        proxy.was_error(e)
        asyncio.create_task(self.proxy_handler.pool.put(proxy))
