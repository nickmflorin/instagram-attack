from __future__ import absolute_import

import asyncio

from instattack import Handler

from .server import CustomBroker
from .pool import CustomProxyPool
from .exceptions import PoolNoProxyError, BrokerNoProxyError, ProxyException


class ProxyHandler(Handler):
    """
    We have to run handler.broker.stop() and handler.broker.find() instead
    of having an async method on ProxyHandler like `start_server()`.  At this point,
    I'm not exactly sure why - but it was causing issues.

    TODO
    ----
    We want to eventually subclass CustomProxyPool more dynamically to use our
    Proxy model and to be able to handle the validation and retrieval logic
    of a proxy.

    Once this is done, self.proxies will not be required anymore because we can
    return directly from self.pool instead of populating results of self.pool
    in self.proxies.
    """
    __subname__ = 'Proxy Handler'

    def __init__(
        self,
        method='GET',
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
    ):
        super(ProxyHandler, self).__init__(method=method)

        self._proxies = proxies or asyncio.Queue()
        self._proxy_limit = proxy_limit

        self._broker = CustomBroker(
            self._proxies,
            method=method,
            max_conn=broker_max_conn,
            max_tries=broker_max_tries,
            timeout=broker_req_timeout,
            verify_ssl=broker_verify_ssl,
            # Our Broker Applies These Args to .find() Manualy
            limit=proxy_limit,
            post=post,
            countries=proxy_countries,
            types=proxy_types,
        )

        self.pool = CustomProxyPool(
            self._broker,
            method=method,
            timeout=proxy_pool_timeout,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=pool_max_error_rate,
            max_resp_time=pool_max_resp_time,
        )

    async def _silent_start(self, loop, prepopulate=True):
        """
        When running in attack mode, we don't want exceptions to be raised when
        we run out of proxies, because the token handler or password handler
        might still be processing them.
        """
        try:
            await asyncio.gather(
                self._broker.find(loop),
                self.pool.start(loop, prepopulate=prepopulate)
            )
        except BrokerNoProxyError as e:
            self.log.warning(e)
        except PoolNoProxyError as e:
            self.log.warning(e)

    async def prepare(self, loop):
        return await self.pool.prepopulate(loop)

    async def start(self, loop, prepopulate=True, silent=False):
        """
        When running concurrently with other tasks/handlers, we don't always
        want to shut down the proxy handler when we hit the limit, because
        the other handler might still be using those.
        """
        async with self._start(loop):
            if silent:
                # We use this when we don't want exceptions to be raised when
                # we run out of proxies.
                await self._silent_start(loop, prepopulate=prepopulate)
            else:
                await asyncio.gather(
                    self._broker.find(loop),
                    self.pool.start(loop, prepopulate=prepopulate)
                )

    async def stop(self, loop, save=False, overwrite=False):
        async with self._stop(loop):
            self._broker.stop()
            await self.pool.stop(loop, save=save, overwrite=overwrite)

    async def get(self):
        if self._stopped:
            raise ProxyException('Cannot get proxy from stopped handler.')
        # PoolNoProxyError will be raised inside of the Pool after a significant
        # timeout, we might want to look at better ways of doing that (i.e. lowering)
        # the timeout once proxies start going into the pool.
        # Otherwise, recognizing that there are no more proxies in the pool could
        # take awhile, since the timeout has to be large enough to start filling
        # it at time 0.
        return await self.pool.get()
