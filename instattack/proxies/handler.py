from __future__ import absolute_import

import asyncio
import stopit

from instattack import exceptions
from instattack.progress import OptionalProgressbar
from instattack.handlers import Handler

from .server import CustomBroker
from .pool import CustomProxyPool
from .exceptions import PoolNoProxyError, NoProxyError
from .utils import write_proxies


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
        proxy_queue_timeout=None,
        proxy_pool_timeout=None,
        proxies=None,
    ):
        super(ProxyHandler, self).__init__(method=method)

        self._stopper = asyncio.Event()

        # We can probably now start splitting these up!
        broker_proxies = asyncio.Queue()
        self.proxies = proxies or asyncio.Queue()

        self._proxy_queue_timeout = proxy_queue_timeout
        self._proxy_limit = proxy_limit

        # When we customize the extension of our CustomProxPool we will probably
        # provide more arguments directly here.
        self.pool = CustomProxyPool(
            broker_proxies,
            method=method,
            timeout=proxy_pool_timeout,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=pool_max_error_rate,
            max_resp_time=pool_max_resp_time,
        )

        self.broker = CustomBroker(
            broker_proxies,
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

    async def start(self, loop):
        return await asyncio.gather(
            self.broker.start(loop),
            self.pool.start(loop),
            self.produce(loop),
        )

    async def produce(self, loop, current_proxies=None, progress=False, display=False):
        """
        Stop event should not be needed since we can break from the cycle
        by putting None into the pool.  If the CustomProxyPool reaches it's limit,
        (defined in the Broker) then PoolNoProxyError will be raised.

        If it has not met it's limit yet, we are intentionally stopping it and
        the value of the retrieved proxy will be None.
        """
        progress = OptionalProgressbar(max_value=self._proxy_limit, enabled=progress)

        with self.log.start_and_done(f'Producing {self.__name__}'):
            # We probably shouldn't need the stop event here since we put None in the
            # queue but just in case.
            while not self._stopped:
                try:
                    proxy = await self.pool.get()

                except PoolNoProxyError as e:
                    self.log.warning(e)
                    progress.finish()
                    await self.stop()
                    break

                else:
                    # See docstring about None value.
                    if proxy is None:
                        self.log.debug('Generator Found Null Proxy')
                        progress.finish()
                        await self.stop()
                        break

                    if display:
                        self.log.info(f'Retrieved Proxy from {self.pool.__name__}', extra={
                            'proxy': proxy,
                            'other': f'Error Rate: {proxy.error_rate}, Avg Resp Time: {proxy.avg_resp_time}' # noqa
                        })
                    progress.update()
                    await self.proxies.put(proxy)

    async def get(self):
        """
        TODO
        ----
        This needs to be consolidated with the proxy pool.

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

        # We want the proxy_queue_timeout to be on the high side when we do not
        # have proxies to load from a collected .txt file.
        with stopit.SignalTimeout(self._proxy_queue_timeout) as timeout_mgr:
            proxy = await self.get_from_queue()

            # This can happen if we run out of proxies when trying to find a token.
            if not proxy:
                raise NoProxyError()
            else:
                self.log.info('THE CHECK BELOW IS NOT WORKING, NO PROXY HAS TIME SINCE USED')
                if proxy and proxy.time_since_used:
                    # TODO: Make this debug level once we are more comfortable with operation.
                    self.log.info('Returning Proxy %s Used %s Seconds Ago' %
                        (proxy.host, proxy.time_since_used))
                return proxy

        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise exceptions.InternalTimeout(
                self._proxy_queue_timeout,
                "Proxy from managed queue. "
                "Consider raising proxy_queue_timeout or adding proxies "
                "ahead of time.")

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
        # We probably shouldn't need the stop event here since we put None in the
        # queue but just in case.
        while not self._stopped:
            proxy = await self.proxies.get()
            if proxy is None:
                break

            # Should we maybe check these verifications before we put the
            # proxy in the queue to begin with?
            if not proxy.last_used:
                return proxy

            # TODO: Move this value to settings.
            elif proxy.time_since_used >= 10:
                return proxy
            else:
                # Put Back in Queue and Keep Going
                await self.proxies.put(proxy)

    async def save(self, overwrite=False):
        """
        TODO: We might want to move this to the pool itself.
        """
        collected = []
        while not self.proxies.empty():
            proxy = await self.proxies.get()
            if proxy is None:
                self.log.warning('Saving Proxies: Found Null Proxy... Removing')
            else:
                collected.append(proxy)

        self.log.notice(f'Saving {len(collected)} Proxies to {self.method.lower()}.txt.')
        write_proxies(self.method, collected, overwrite=overwrite)

    async def stop(self):
        with self.log.start_and_done(f"Stopping {self.__name__}"):
            self._stopper.set()
            self.broker.stop()

            # Have to do before we stop pool otherwise the handler will try to get
            # a proxy from the stopped pool.
            await self.proxies.put(None)
            await self.pool.stop()

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
    def _stopped(self):
        return self._stopper.is_set()
