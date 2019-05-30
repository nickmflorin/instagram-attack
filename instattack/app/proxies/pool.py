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

    def __init__(self, config, broker, start_event=None):
        # We do not want to restrict the size of the Proxy Pool because it can
        # be detrimental for larger attack sizes.
        super(ProxyPool, self).__init__(-1)

        self.broker = broker
        self.config = config
        self.start_event = start_event
        self.timeout = self.config['proxies']['pool']['timeout']

        self.lock = asyncio.Lock()

        # Proxies that we want to wait for a little while until we put back
        # in the queue.
        self.on_hold = []

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()
        self.last_logged_qsize = None

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        log = self.create_logger('prepopulate')
        await log.start('Prepopulating Proxies')

        async for proxy in stream_proxies(self.config):
            proxy.reset()

            evaluation = proxy.evaluate_for_pool(self.config)
            if evaluation.passed:
                await self.put(proxy)

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
        log = self.create_logger('collect')

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

    @property
    def num_proxies(self):
        return self.qsize() + len(self.on_hold)

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
        log = self.create_logger('get')
        try:
            if self.num_proxies <= 20:
                if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                    self.last_logged_qsize = self.num_proxies
                    await log.warning(f'Running Low on Proxies: {self.num_proxies}')

            # [x] TODO:
            # We do not necessarily want to raise the error immediatley if the
            # queue is empty, since more proxies may be in the process of being added
            # or about to be added, but we should kick start collection here if we
            # are running low.
            proxy = await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()
        else:
            return proxy

    async def _get_from_hold(self):
        """
        [x] TODO:
        --------
        Another option to the .hold() methodology might be to have a confirmed
        queue and an unconfirmed queue, where the priority for the confirmed
        queue emphasizes only time since used, which is not a priority value of
        the unconfirmed queue.
        """
        for proxy in self.on_hold:
            hold = proxy.hold(self.config)
            if not hold:
                self.on_hold.remove(proxy)
                return proxy

    async def _get_proxy(self):
        """
        Retrieves the lowest priority proxy from the queue that is ready to
        be used.
        """
        log = self.create_logger('get')

        # [x] TODO:
        # This can sometimes drag on for awhile toward the end, we need to figure
        # out how to fix that...
        while True:
            proxy = await self._get_from_hold()
            if proxy:
                return proxy

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
        -------------
        Sometimes we might want to still add the proxy even if the
        quantitative metrics aren't perfect, but we know the proxy has
        successful requests -> Reason for Strict Parameter

        [x] TODO:
        --------
        Another option to the .hold() methodology might be to have a confirmed
        queue and an unconfirmed queue, where the priority for the confirmed
        queue emphasizes only time since used, which is not a priority value of
        the unconfirmed queue.
        """
        log = self.create_logger('get')

        evaluation = proxy.evaluate_for_pool(self.config)
        if evaluation.passed:
            if proxy.hold(self.config):
                async with self.lock:
                    await log.debug('Putting Proxy in Hold')
                    self.on_hold.append(proxy)
            else:
                await self.put(proxy)
        else:
            log.debug('Discarding Proxy')

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
        priority = proxy.priority(count, self.config)
        await super(ProxyPool, self).put((priority, proxy))
        return proxy
