import asyncio
import aiojobs
import itertools

from instattack.app.exceptions import PoolNoProxyError
from instattack.app.mixins import LoggerMixin

from .utils import stream_proxies


"""
[!] IMPORTANT:
-------------

In the long run, it might be best to eventually separate into multiple queues,
for failed proxies, confirmed proxies and non confirmed proxies, pulling from
the desired queues based on priority.
"""


class ProxyPool(asyncio.PriorityQueue, LoggerMixin):

    __name__ = 'Proxy Pool'
    __logconfig__ = 'proxy_pool'

    def __init__(self, config, broker, start_event=None):
        super(ProxyPool, self).__init__(config.get('limit', -1))

        self.broker = broker
        self.config = config
        self.start_event = start_event

        self.timeout = self.config['proxies']['pool']['timeout']

        # Not Using This Right Now
        self.prepopulate_limit = None

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        async with self.async_logger('prepopulate') as log:
            await log.start('Prepopulating Proxies')

            async for proxy in stream_proxies(self.config):
                proxy.reset()

                evaluation = proxy.evaluate_for_pool(self.config)
                if evaluation.passed:
                    await self.put(proxy)
                    if self.prepopulate_limit and self.qsize() == self.prepopulate_limit:
                        break

            if self.qsize() == 0:
                await log.error('No Proxies to Prepopulate')
                return

            await log.complete(f"Prepopulated {self.qsize()} Proxies")

    async def collect(self, loop):
        """
        Retrieves proxies from the broker and converts them to our Proxy model.
        The proxy is then evaluated as to whether or not it meets the standards
        specified and conditionally added to the pool.

        [!] IMPORTANT:
        -------------
        We should maybe make this more dynamic, and add proxies from the broker
        when the pool drops below the limit.

        Figure out how to make the collect limit more dynamic, or at least calculated
        based on the prepopulated limit.
        >>> collect_limit = max(self._maxsize - self.qsize(), 0)
        """
        async with self.async_logger('collect') as log:
            await log.start('Collecting Proxies')

            scheduler = await aiojobs.create_scheduler(limit=None)

            count = 0
            collect_limit = 10000  # Arbitrarily high for now.

            async for proxy, created in self.broker.collect(loop, save=True, scheduler=scheduler):
                evaluation = proxy.evaluate_for_pool(self.config)
                if evaluation.passed:
                    await self.put(proxy)

                    # Set Start Event on First Proxy Retrieved from Broker
                    if self.start_event and not self.start_event.is_set():
                        self.start_event.set()
                        await log.info('Setting Start Event', extra={
                            'other': 'Broker Started Sending Proxies'
                        })

                if collect_limit and count == collect_limit:
                    break
                count += 1

    async def get(self):
        """
        Remove and return the lowest priority proxy in the pool. Raise KeyError
        if empty and a TimeoutError if it is taking too long.

        [!] IMPORTANT:
        -------------
        We need to figure out a way to trigger more proxies from being collected
        if we wind up running out of proxies - this might involve adjusting the
        timeout so it does not think there are no more proxies when they are just
        all currently being used.

        We should also only log that message periodically.

        [x] TODO:
        ---------
        Once pool reaches a certain size, we should automatically break out of
        the while loop instead of waiting the full self._timeout value - that
        way we know faster if we do not have any proxies left.

        >>> while True:
        >>>     if not self._pool:
        >>>         if self._prepopulated and self._threshold:
        >>>             raise PoolNoProxyError()
        >>>     else:
        >>>         if len(self._pool) >= self._min_threshold:
        >>>             self._threshold = True
        >>>         ...
        """
        async with self.async_logger('get') as log:
            try:
                if self.qsize() <= 20:
                    await log.warning(f'Running Low on Proxies: {self.qsize()}')

                # We might not need this timeout, since it might be factored into the
                # session already.
                proxy = await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
            except asyncio.TimeoutError:
                raise PoolNoProxyError()
            else:
                return proxy

    async def _get_proxy(self):
        """
        Retrieves the lowest priority proxy from the queue that is ready to
        be used.
        """
        async with self.async_logger('get') as log:
            while True:
                ret = await super(ProxyPool, self).get()
                proxy = ret[1]

                evaluation = proxy.evaluate_for_use(self.config)
                if not evaluation.passed:
                    await log.debug('Cannot Use Proxy from Pool', extra={
                        'proxy': proxy,
                        'other': str(evaluation),
                    })
                else:
                    return proxy

    async def check_and_put(self, proxy):
        """
        [!] IMPORTANT:
        Sometimes we might want to still add the proxy even if the
        quantitative metrics aren't perfect, but we know the proxy has
        successful requests.
        """
        async with self.async_logger('put') as log:
            evaluation = proxy.evaluate_for_pool(self.config)
            if not evaluation.passed:
                await log.warning('Cannot Add Proxy to Pool', extra={
                    'proxy': proxy,
                    'other': str(evaluation),
                })
            else:
                await self.put(proxy)

    async def put(self, proxy):
        """
        Adds proxy to the pool and keeps record in proxy_finder for accessing
        at later point.

        [!] IMPORTANT:
        -------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """
        count = next(self.proxy_counter)
        priority = proxy.priority(count)
        await super(ProxyPool, self).put((priority, proxy))
        return proxy