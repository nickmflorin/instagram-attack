import asyncio
import itertools

from instattack import logger
from .exceptions import PoolNoProxyError


log = logger.get_async('Proxy Priority Queue')


"""
TODO
----
This can definitely be simplified.  Since we do not put duplicate proxies
in the queue, by default, we probably don't need to worry about tracking
the REMOVED status, and can just not put back in the queue if it is invalid
on put, and keep looking if it is not valid on get.
"""

"""
IMPORTANT
---------
Instead of using the priority of the proxy for everything, separate into two
queues, "confirmed" and "unconfirmed" and "invalid", and pull from those in
priority.
"""


class ProxyPriorityQueue(asyncio.PriorityQueue):

    REMOVED = '<removed-proxy>'
    DEFAULT_TIMEOUT = 25

    def __init__(self, config):
        super(ProxyPriorityQueue, self).__init__(config.get('limit', -1))

        self.log_queue = config.get('log', False)
        self.timeout = config.get('timeout', self.DEFAULT_TIMEOUT)

        # Right now, we haven't really figured out a better meaning for `strict`
        # other than the fact that it means the proxy will be removed/not put
        # in queue.  This is kind of pointless because we could also just not
        # include the `value`, but we might have better reasons for `strict` soon.
        self.exclusion = {
            'max_error_rate': config.get('max_error_rate', {'strict': False}),
            'max_resp_time': config.get('max_resp_time', {'strict': False}),
            'min_req_proxy': config.get('min_req_proxy', {'strict': False}),
        }

        # Mapping of proxies to entries in the heapq
        self.proxy_finder = {}

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()

    async def put(self, proxy, source=None):
        log = logger.get_async('Proxy Priority Queue', subname='put')

        # See Note Above About `strict`
        evaluations = proxy.evaluate(**self.exclusion)

        invalid = False
        if len(evaluations) != 0:
            invalid = any([evalu['strict'] for evalu in evaluations])

        current = self.proxy_finder.get(proxy.unique_id)

        if invalid:
            if current:
                if current != self.REMOVED:
                    log.warning('Have to Remove Invalid Proxy from Pool', extra={
                        'proxy': proxy,
                        'other': f"Pool Size: {self.qsize()}",
                        'list': [evalu['reason'] for evalu in evaluations]
                    })
                    await self._remove_proxy(proxy)
            else:
                # [!] IMPORTANT:  Maybe instead of not adding, we should still add,
                # since the proxy will be towards the back of the queue due to
                # priority - this alleviates the risk of running out of proxies
                # which we have been seeing for large numbers of attempts.
                #
                # This is sort of what the `strict` parameter is doing right now.
                log.warning('Cannot Add Proxy to Pool', extra={
                    'proxy': proxy,
                    'other': f"Pool Size: {self.qsize()}",
                    'list': [evalu['reason'] for evalu in evaluations]
                })
                pass
            return None

        log.disable_on_false(self.log_queue)

        current = self.proxy_finder.get(proxy.unique_id)

        # Second equality just added, think it is right.
        if not current or current == self.REMOVED:
            log.debug('Adding New Proxy to Pool', extra={
                'proxy': proxy,
                'other': f"Pool Size: {self.qsize()}"
            })
            return await self._put_proxy(proxy)

        # Only want to include proxy if it is fundamentally different
        # than proxies we have already.
        differences = current.compare(proxy, return_difference=True)
        if differences:
            log.debug('Updating Proxy in Pool', extra={
                'proxy': proxy,
                'other': str(differences) + ' ' + f"Pool Size: {self.qsize()}"
            })
            return await self._update_proxy(current, proxy)

        # No Proxy Updated, Return None
        return None

    async def get(self):
        """
        Remove and return the lowest priority proxy in the pool. Raise KeyError
        if empty.

        This should still work even when the pool is "stopped", because "stopped"
        just means that the Broker is no longer being used to populate the pool,
        not that the pool should be empty and not accessible by its consumers.

        TODO:
        ----
        The timeout value needs to be large enough so that the Broker can spin
        up and start populating the pool.  However, we probably want to find
        a way to shorten it after the pool is populated, so we are not waiting
        forever with an empty pool.

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
        try:
            # We might not need this timeout, since it might be factored into the
            # session already.
            if self.qsize() <= 20:
                log.info(f'Running Low on Proxies: {self.qsize()}')
            proxy = await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()
        else:
            return proxy

    async def _get_proxy(self):
        """
        We might eventually want to incorporate these into the actual prioritization
        of the proxy, instead of absolute limiting factors on the retrieval of
        the proxy.

        If we don't incorporate this into the retrieval though, the proxy will
        keep being used over and over again at the start (if not prepopulating,
        because collection is slower).
        """
        while True:
            ret = await super(ProxyPriorityQueue, self).get()
            proxy = ret[1]

            try:
                current = self.proxy_finder[proxy.unique_id]
            except KeyError:
                log.critical(
                    f'Proxy {proxy.unique_id} Missing from Proxy Finder... Should be Present.')
            else:
                if current is not self.REMOVED:
                    if not proxy.last_used or proxy.time_since_used >= 20:
                        del self.proxy_finder[proxy.unique_id]
                        return proxy

    async def _put_proxy(self, proxy):
        """
        Adds proxy to the pool and keeps record in proxy_finder for accessing
        at later point.
        """

        # Tuple comparison for priority in Python3 breaks if two tuples are the
        # same, so we have to use a counter to guarantee that no two tuples are
        # the same and priority will be given to proxies placed first.
        count = next(self.proxy_counter)
        self.proxy_finder[proxy.unique_id] = proxy
        priority = proxy.priority(count)
        await super(ProxyPriorityQueue, self).put((priority, proxy))
        return proxy

    async def _remove_proxy(self, proxy):
        """
        Mark an existing proxy as REMOVED. Raise KeyError if not found.

        Marking as REMOVED is necessary because in order to update a proxy
        priority in the queue, this is because we cannot simply update or remove
        the entry from the PriorityQueue.

        TODO:
        ----
        What to do if we are updating a proxy in the pool that was REMOVED
        but is no longer "REMOVED" since it is now valid again.
        """
        self.proxy_finder[proxy.unique_id] = self.REMOVED

    async def _update_proxy(self, old_proxy, proxy):
        """
        Updates a proxy in the pool by first marking the original proxy as
        REMOVED and then adding the new proxy.
        """
        await self._remove_proxy(old_proxy)
        return await self._put_proxy(proxy)
