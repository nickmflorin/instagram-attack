import asyncio

from lib import coro_exc_wrapper
from instattack.exceptions import ProxyException
from instattack.handlers.base import Handler

from .broker import CustomBroker
from .pool import CustomProxyPool


class ProxyHandler(Handler):

    __name__ = 'Proxy Handler'

    def __init__(
        self,
        # Broker Arguments
        broker_req_timeout=None,
        broker_max_conn=None,
        broker_max_tries=None,
        broker_verify_ssl=None,
        # Find Arguments
        proxy_limit=None,
        post=False,
        proxy_countries=None,
        proxy_types=None,
        # Pool Arguments
        pool_min_req_proxy=None,
        pool_max_error_rate=None,
        pool_max_resp_time=None,
        # Handler Args
        proxy_pool_timeout=None,
        proxies=None,
        **kwargs,
    ):
        super(ProxyHandler, self).__init__(**kwargs)

        self._proxies = proxies or asyncio.Queue()
        self._proxy_limit = proxy_limit

        self._broker = CustomBroker(
            self._proxies,
            max_conn=broker_max_conn,
            max_tries=broker_max_tries,
            timeout=broker_req_timeout,
            verify_ssl=broker_verify_ssl,
            # Our Broker Applies These Args to .find() Manualy
            limit=proxy_limit,
            post=post,
            countries=proxy_countries,
            types=proxy_types,
            **kwargs,
        )

        self.pool = CustomProxyPool(
            self._proxies,
            self._broker,
            timeout=proxy_pool_timeout,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=pool_max_error_rate,
            max_resp_time=pool_max_resp_time,
            **kwargs,
        )

    async def run(self, loop, **kwargs):
        """
        NOTE:
        -----
        When running concurrently with other tasks/handlers, we don't always
        want to shut down the proxy handler when we hit the limit, because
        the other handler might still be using those.

        TODO:
        ----
        Test the operation without prepopulation, since it sometimes
        slows down too much when we are waiting on proxies from the finder.
        """
        async with self.starting(loop):
            await asyncio.gather(
                self._broker.find(loop),
                self.pool.run(loop, **kwargs)
            )

    async def stop(self, loop):
        """
        The pool will stop on it's own, once it realizes that there are no
        more proxies in the broker.
        """
        self._broker.stop(loop)
        self._stopped = True

    async def get(self):
        if self._stopped:
            raise ProxyException('Cannot get proxy from stopped handler.')
        return await self.pool.get()

    async def save(self, overwrite=False):
        return await self.pool.save(overwrite=overwrite)
