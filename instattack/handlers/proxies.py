from __future__ import absolute_import

import asyncio

from urllib.parse import urlparse

import stopit

from instattack import exceptions
from instattack.conf import settings

from instattack.proxies import CustomBroker, CustomProxyPool
from instattack.proxies.exceptions import NoProxyError, ProxyException
from instattack.proxies.utils import read_proxies, filter_proxies
from instattack.proxies.models import Proxy

from .base import Handler


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
    __name__ = 'Proxy Handler'

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
        proxy_max_error_rate=None,
        proxy_max_resp_time=None,
        # Handler Args
        proxy_queue_timeout=None,
        proxy_pool_timeout=None,
        proxies=None,
    ):
        super(ProxyHandler, self).__init__(f'{method} {self.__name__}')

        self.method = method

        self._proxy_queue_timeout = proxy_queue_timeout
        self._proxy_pool_timeout = proxy_pool_timeout

        # Pool Arguments
        self._proxy_max_error_rate = proxy_max_error_rate
        self._proxy_max_resp_time = proxy_max_resp_time

        broker_proxies = asyncio.Queue()
        self.proxies = proxies or asyncio.Queue()

        # When we customize the extension of our CustomProxPool we will probably
        # provide more arguments directly here.
        self.pool = CustomProxyPool(
            broker_proxies,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=self._proxy_max_error_rate,
            max_resp_time=self._proxy_max_resp_time,
        )

        self.broker = CustomBroker(
            broker_proxies,
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

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        with self.log.start_and_done(f'Prepopulating {self.method} Proxies'):
            proxies = read_proxies(method=self.method)
            for proxy in filter_proxies(
                proxies,
                max_error_rate=self._proxy_max_error_rate,
                max_resp_time=self._proxy_max_resp_time
            ):
                await self.proxies.put(proxy)

    async def produce(self, loop):
        """
        Stop event should not be needed since we can break from the cycle
        by putting None into the pool.  If the CustomProxyPool reaches it's limit,
        (defined in the Broker) then NoProxyError will be raised.

        If it has not met it's limit yet, we are intentionally stopping it and
        the value of the retrieved proxy will be None.
        """
        with self.log.start_and_done(f'Producing {self.method} Proxies'):
            async for proxy in self.get_from_pool():
                if proxy is None:
                    raise ProxyException("Should not have None values in generator.")
                await self.proxies.put(proxy)
        # Should we have a self.stop() call here?

    async def _get_from_pool(self, max_error_rate=None, max_resp_time=None):
        # Leave these optional now for flexibility - this can be useful to use
        # outside of this class.
        max_error_rate = max_error_rate or self._proxy_max_error_rate
        max_resp_time = max_resp_time or self._proxy_max_resp_time

        # If we are not filtering by the metrics (which should be done automatically
        # in the pool) than we probably don't need SignalTimeout.
        self.log.debug('Waiting on Proxy from Pool...')
        proxy = await self.pool.get(scheme=self.scheme)
        self.log.debug('Got Proxy from Pool...')

        if not proxy:
            self.log.debug('Proxy Pool Returned None')
            return None

        # TODO: Make it so that the pool works with our model of Proxy and
        # our model of Proxy includes additional info.
        _proxy = Proxy(
            host=proxy.host,
            port=proxy.port,
            avg_resp_time=proxy.avg_resp_time,
            error_rate=proxy.error_rate,
            is_working=proxy.is_working,
        )
        return _proxy

    async def get_from_pool(self, max_error_rate=None, max_resp_time=None):
        # Maybe add optional limit argument that can override the Pool limit?
        max_error_rate = max_error_rate or self._proxy_max_error_rate
        max_resp_time = max_resp_time or self._proxy_max_resp_time

        while True:
            try:
                self.log.debug('Retrieving Proxy from Pool')
                with stopit.SignalTimeout(self._proxy_pool_timeout) as timeout_mgr:
                    proxy = await self._get_from_pool(
                        max_error_rate=max_error_rate,
                        max_resp_time=max_resp_time
                    )
                if timeout_mgr.state == timeout_mgr.TIMED_OUT:
                    raise exceptions.InternalTimeout(
                        "Timed out waiting for a proxy from pool."
                    )

            # Weird error from ProxyBroker that makes no sense...
            # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
            except TypeError as e:
                self.log.warning(e)
                continue

            except NoProxyError as e:
                self.log.warning(e)
                await self.stop()
                break

            else:
                # See docstring about None value.
                if proxy is None:
                    self.log.debug('Generator Found Null Proxy')
                    await self.stop()
                    break

                self.log.debug('Generator Yielding Proxy', extra={'proxy': proxy})
                yield proxy

    async def get_from_queue(self):
        """
        Retrieves proxy from our personally maintained queue.  If the value is
        None, the consumer was intentionally stopped so we want to break out
        of the loop.

        TODO
        ----
        We might not need to validate certain aspects of the proxy because some
        of it should be handled by the CustomProxyPool.
        """
        while True:
            proxy = await self.proxies.get()
            if proxy is None:
                break

            # Should we maybe check these verifications before we put the
            # proxy in the queue to begin with?
            if not proxy.last_used:
                return proxy
            elif proxy.time_since_used() >= 10:
                return proxy
            else:
                # Put Back in Queue and Keep Going
                await self.proxies.put(proxy)

    async def get(self):
        """
        TODO
        ----
        We want to eventually incorporate this type of logic into the ProxyPool
        so that we can more easily control the queue output.

        We should be looking at prioritizing proxies by `confirmed = True` where
        the time since it was last used is above a threshold (if it caused a too
        many requests error) and then look at metrics.

        import heapq

        data = [
            ((5, 1, 2), 'proxy1'),
            ((5, 2, 1), 'proxy2'),
            ((3, 1, 2), 'proxy3'),
            ((5, 1, 1), 'proxy5'),
        ]

        heapq.heapify(data)
        for item in data:
            print(item)

        We will have to re-heapify whenever we go to get a proxy (hopefully not
        too much processing) - if it is, we should limit the size of the proxy queue.

        Priority can be something like (x), (max_resp_time), (error_rate), (times used)
        x is determined if confirmed AND time since last used > x (binary)
        y is determined if not confirmed and time since last used > x (binary)

        Then we will always have prioritized by confirmed and available, not confirmed
        but ready, all those not used yet... Might not need to prioritize by times
        not used since that is guaranteed (at least should be) 0 after the first
        two priorities
        """
        # with stopit.SignalTimeout(self._proxy_queue_timeout) as timeout_mgr:
        proxy = await self.get_from_queue()
        self.log.info('THE CHECK BELOW IS NOT WORKING, NO PROXY HAS TIME SINCE USED')
        if proxy and proxy.time_since_used:
            # TODO: Make this debug level once we are more comfortable
            # with operation.
            self.log.info('Returning Proxy %s Used %s Seconds Ago' %
                (proxy.host, proxy.time_since_used))

        # if timeout_mgr.state == timeout_mgr.TIMED_OUT:
        #     raise exceptions.InternalTimeout("Timed out waiting for a valid proxy.")

        return proxy

    async def stop(self):
        self.log.notice(f'Stopping {self.method} Server.')
        self.broker.stop()

        self.log.notice(f'Stopping {self.method} Proxy Pool.')
        await self.pool.stop()

        self.log.notice(f'Stopping {self.method} {self.__name__}.')
        self.proxies.put_nowait(None)

    async def confirmed(self, proxy):
        proxy.update_time()
        proxy.confirmed = True
        proxy.times_used += 1
        await self.proxies.put(proxy)

    async def used(self, proxy):
        """
        When we want to keep proxy in queue because we're not sure if it is
        invalid (like when we get a Too Many Requests error) but we don't want
        to note it as `confirmed` just yet.
        """
        proxy.update_time()
        proxy.times_used += 1
        await self.proxies.put(proxy)

    @property
    def scheme(self):
        return urlparse(settings.URLS[self.method]).scheme

    @property
    def stopped(self):
        return self.broker._server is None

    @property
    def running(self):
        return not self.stopped
