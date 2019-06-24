import asyncio
import itertools

from instattack import settings

from instattack.lib import logger

from instattack.core.exceptions import PoolNoProxyError
from instattack.core.proxies.interfaces import ProxyQueueInterface


__all__ = (
    'SimpleProxyPool',
    'ManagedProxyPool'
)


class ProxyPriorityQueue(asyncio.PriorityQueue, ProxyQueueInterface):

    def __init__(self, loop):
        super(ProxyPriorityQueue, self).__init__(-1)

        self.loop = loop
        self.last_logged_qsize = None

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()
        self.timeout = settings.proxies.pool.pool_timeout

    async def contains(self, proxy):
        return proxy in [item[1] for item in self._queue]

    async def log_pool_size(self):
        """
        Log Running Low on Proxies Periodically if Change Noticed
        """
        if self.num_proxies <= 20:
            if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                self.log.warning(f'Running Low on Proxies: {self.num_proxies}')
                self.last_logged_qsize = self.num_proxies

    async def get(self):
        """
        Remove and return the lowest priority proxy in the pool.
        Raise a PoolNoProxyError if it is taking too long - which just means
        there are no more proxies.

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

    async def _get_proxy(self):
        """
        Proxies are always evaluated before being put in queue so we do
        not have to reevaluate.
        """
        ret = await super(ProxyPriorityQueue, self).get()
        proxy = ret[1]
        await self.log_pool_size()
        return proxy


class AbstractProxyPool(ProxyPriorityQueue):

    __queueid__ = 'pool'

    # def validate_for_queue(self, proxy):
    #     evaluation = proxy.evaluate_for_pool()
    #     if not evaluation.passed:
    #         return False
    #     return True


class SimpleProxyPool(AbstractProxyPool):

    __NAME__ = "Simple Proxy Pool"
    log = logger.get(__name__, __NAME__)


class ManagedProxyPool(SimpleProxyPool):

    __NAME__ = "Managed Proxy Pool"
    log = logger.get(__name__, __NAME__)

    async def put(self, proxy, evaluate=True, prepopulation=False):
        """
        [x] NOTE:
        ---------
        We do not want to check confirmation based on the threshold and horizon,
        because that is the definition for confirmed proxies, which should not
        be put in the general pool.
        """
        if evaluate:
            evaluation = proxy.evaluate_for_pool()
            if evaluation.passed:
                await super(ManagedProxyPool, self).put(proxy)
            else:
                # Do not log during prepopulation.
                if not prepopulation:
                    if settings.logging.log_proxy_queue:
                        self.log.debug(f'Cannot Add Proxy to {self.__NAME__}', extra={
                            'other': str(evaluation)
                        })

                    if proxy.confirmed():
                        self.log.warning('Removing Proxy That Was Confirmed from Pool', extra={
                            'proxy': proxy,
                        })
