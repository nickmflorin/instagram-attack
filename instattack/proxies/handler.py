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
            self._proxies,
            self._broker,
            method=method,
            timeout=proxy_pool_timeout,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=pool_max_error_rate,
            max_resp_time=pool_max_resp_time,
        )

    async def run(self, loop, save=False, overwrite=False, prepopulate=True):
        # TODO: Figure out when we would run into issues with the pool vs. the
        # broker running out or proxies.  It should always hit BrokerNoProxyError
        # first, I think?
        try:
            await self.start(loop, prepopulate=prepopulate)
        except BrokerNoProxyError as e:
            self.log.notice(e)
        except PoolNoProxyError as e:
            self.log.warning(e)
        finally:
            await self.stop(loop, save=save, overwrite=overwrite)

    async def start(self, loop, prepopulate=True):
        async with self._start(loop):
            self._broker.start(loop)
            asyncio.create_task(self.pool.start(loop, prepopulate=prepopulate))

    async def ensure_shutdown(self, loop, save=False, overwrite=False):
        if not self._stopped:
            self.log.warning(f'{self.__name__} was never shutdown.')
        return await self.stop(loop, save=save, overwrite=overwrite)

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
