from __future__ import absolute_import

import asyncio

from instattack import OptionalProgressbar, Handler

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

        # When we customize the extension of our CustomProxPool we will probably
        # provide more arguments directly here.
        self.pool = CustomProxyPool(
            self._proxies,
            method=method,
            timeout=proxy_pool_timeout,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=pool_max_error_rate,
            max_resp_time=pool_max_resp_time,
        )

        self.broker = CustomBroker(
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

    async def run(self, loop, save=False, overwrite=False):
        try:
            await self.start(loop)
        except BrokerNoProxyError as e:
            self.log.notice(e)
        finally:
            await self.stop(loop, save=save, overwrite=overwrite)

    async def start(self, loop):
        async with self._start(loop):
            return await asyncio.gather(
                self.broker.start(loop),
                self.pool.start(loop),
            )

    async def stop(self, loop, save=False, overwrite=False):
        async with self._stop(loop):
            self.broker.stop()
            await self.pool.stop(loop, save=save, overwrite=overwrite)

    async def produce(self, loop, current_proxies=None, progress=False, display=False):
        """
        Stop event should not be needed since we can break from the cycle
        by putting None into the pool.  If the CustomProxyPool reaches it's limit,
        (defined in the Broker) then PoolNoProxyError will be raised.

        If it has not met it's limit yet, we are intentionally stopping it and
        the value of the retrieved proxy will be None.
        """
        progress = OptionalProgressbar(max_value=self._proxy_limit, enabled=progress)

        # We probably shouldn't need the stop event here since we put None in the
        # queue but just in case.
        while not self._stopped:
            try:
                proxy = await self.pool.get()

            except PoolNoProxyError as e:
                self.log.warning(e)
                progress.finish()
                await self.stop(loop)
                break

            # I think here instead of stopping we are just going to want to
            # stop the broker maybe...
            except BrokerNoProxyError as e:
                self.log.warning(e)
                progress.finish()
                await self.stop(loop)
                break

            else:
                # See docstring about None value.
                if proxy is None:
                    self.log.debug('Generator Found Null Proxy')
                    progress.finish()
                    await self.stop(loop)
                    break

                if display:
                    self.log.info(f'Retrieved Proxy from {self.pool.__name__}', extra={
                        'proxy': proxy,
                        'other': f'Error Rate: {proxy.error_rate}, Avg Resp Time: {proxy.avg_resp_time}' # noqa
                    })
                progress.update()
                await self.proxies.put(proxy)

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

    async def confirmed(self, proxy):
        proxy.update_time()
        proxy.confirmed = True
        proxy.times_used += 1
        await self.pool.put(proxy)

    async def used(self, proxy):
        """
        When we want to keep proxy in queue because we're not sure if it is
        invalid (like when we get a Too Many Requests error) but we don't want
        to note it as `confirmed` just yet.
        """
        proxy.update_time()
        proxy.times_used += 1
        await self.pool.put(proxy)
