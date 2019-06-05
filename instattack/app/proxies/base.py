import asyncio
import itertools

from instattack.config import config
from instattack.app.exceptions import ProxyPoolError, PoolNoProxyError


class ProxyQueue(asyncio.Queue):

    def __init__(self):
        super(ProxyQueue, self).__init__(-1)

    @property
    def num_proxies(self):
        return self.qsize()

    async def put(self, proxy):
        proxy.queue_id = self.__queueid__
        await super(ProxyQueue, self).put(proxy)


class ProxyPriorityQueue(asyncio.PriorityQueue):

    def __init__(self):
        super(ProxyPriorityQueue, self).__init__(-1)

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()
        self.timeout = config['pool']['timeout']

    @property
    def num_proxies(self):
        return self.qsize()

    async def put(self, proxy):
        """
        [!] IMPORTANT:
        -------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """
        count = next(self.proxy_counter)
        priority = proxy.priority(count)
        proxy.queue_id = self.__queueid__
        await super(ProxyPriorityQueue, self).put((priority, proxy))

    async def get(self):
        """
        Remove and return the lowest priority proxy in the pool.
        Raise a PoolNoProxyError if it is taking too long.

        [x] NOTE:
        --------
        We do not want to raise PoolNoProxyError if the queue is immediately
        empty - there may be proxies in use that will momentarily be put back
        in queue.

        [!] TODO:
        --------
        We need to figure out a way to trigger more proxies from being collected
        if we wind up running out of proxies - or turn on collection if we run
        out of proxies.
        """
        try:
            return await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()

    async def _get_proxy(self):
        """
        Proxies are always evaluated before being put in queue so we do
        not have to reevaluate.
        """
        ret = await super(ProxyPriorityQueue, self).get()
        proxy = ret[1]
        return proxy


class ProxySubQueue(ProxyQueue):

    __queueid__ = None

    def __init__(self, pool):
        super(ProxySubQueue, self).__init__()
        self.pool = pool
        self.lock = asyncio.Lock()

    async def contains(self, proxy):
        return proxy in self._queue

    async def raise_if_missing(self, proxy):
        """
        Most likely a temporary utility.
        Raises ProxyPoolError if a proxy is expected in the queue but is not
        found.
        """
        if not await self.contains(proxy):
            raise ProxyPoolError(f'Expected Proxy to be in {self.__name__}')

    async def raise_if_present(self, proxy):
        """
        Most likely a temporary utility.
        Raises ProxyPoolError if a proxy is not expected in the queue but is
        found.
        """
        if await self.contains(proxy):
            raise ProxyPoolError(f'Did Not Expect Proxy to be in {self.__name__}')

    async def warn_if_missing(self, proxy):
        """
        Most likely a temporary utility.
        Warns if a proxy is expected in the queue but is not found.
        """
        try:
            await self.raise_if_missing(proxy)
        except ProxyPoolError as e:
            self.log.warning(e)
            return True
        else:
            return False

    async def warn_if_present(self, proxy):
        """
        Most likely a temporary utility.
        Warns if a proxy is not expected in the queue but is found.
        """
        try:
            await self.raise_if_present(proxy)
        except ProxyPoolError as e:
            self.log.warning(e)
            return True
        else:
            return False


class AbstractProxyPool(ProxyPriorityQueue):

    __queueid__ = 'pool'

    def __init__(self, loop, start_event=None):
        super(AbstractProxyPool, self).__init__()

        self.loop = loop
        self.start_event = start_event

        self.last_logged_qsize = None
        self.original_num_proxies = 0

    async def log_pool_size(self):
        """
        Log Running Low on Proxies Periodically if Change Noticed
        """
        if self.num_proxies <= 20:
            if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                self.log.warning(f'Running Low on Proxies: {self.num_proxies}')
                self.last_logged_qsize = self.num_proxies
