import asyncio
import itertools

from instattack import logger
from .exceptions import PoolNoProxyError


log = logger.get_async('Proxy Priority Queue')


class ProxyLoggerAdapter(object):

    def format_message(self, message, source=None):
        if 'Source' in message:
            if source is not None:
                message = message.replace('Source', source)
            else:
                message = message.replace('Source ', '')
        return message

    def warn(self, queue, message, proxy, source=None, other=None, force=False):
        message = self.format_message(message, source=source)
        extra = {
            'proxy': proxy,
            'other': (other or "") + f"Pool Size: {queue.qsize()}"
        }
        log.warning(message, extra=extra)

    def info(self, queue, message, proxy, source=None, other=None, force=False):
        message = self.format_message(message, source=source)
        extra = {
            'proxy': proxy,
            'other': (other or "") + f"Pool Size: {queue.qsize()}"
        }
        log.info(message, extra=extra)

    def debug(self, queue, message, proxy, source=None, other=None, force=False):
        message = self.format_message(message, source=source)
        extra = {
            'proxy': proxy,
            'other': (other or "") + f"Pool Size: {queue.qsize()}"
        }
        log.debug(message, extra=extra)


log = log.adapt(ProxyLoggerAdapter)


class ProxyPriorityQueue(asyncio.PriorityQueue):

    REMOVED = '<removed-proxy>'

    def __init__(self, config):
        super(ProxyPriorityQueue, self).__init__(config['proxies'].get('limit', -1))

        log.disable_on_false(config['log'].get('proxies', False))

        self.max_error_rate = config['proxies']['pool']['max_error_rate']
        self.max_resp_time = config['proxies']['pool']['max_resp_time']
        self.min_req_proxy = config['proxies']['pool']['min_req_proxy']
        self.timeout = config['proxies']['pool']['timeout']

        # Mapping of proxies to entries in the heapq
        self.proxy_finder = {}

        # The entry count serves as a tie-breaker so that two tasks with the
        # same priority are returned in the order they were added.
        # And since no two entry counts are the same, the tuple comparison will
        # never attempt to directly compare two tasks.
        self.proxy_counter = itertools.count()

    async def put(self, proxy, source=None):
        valid, reason = proxy.evaluate(
            num_requests=self.min_req_proxy,
            error_rate=self.max_error_rate,
            resp_time=self.max_resp_time,
        )

        if not valid:
            current = self.proxy_finder.get(proxy.unique_id)
            if current and current != self.REMOVED:
                log.warning(self, 'Have to Remove Invalid Source Proxy from Pool',
                    proxy, source=source, other=reason, force=True)
                await self._remove_proxy(proxy, invalid=True, reason=reason)
            else:
                log.warning(self, 'Cannot Add Source Proxy to Pool',
                    proxy, source=source, other=reason)
            return None

        current = self.proxy_finder.get(proxy.unique_id)
        if not current:
            log.info(self, 'Adding New Source Proxy to Pool', proxy, source=source)
            return await self._put_proxy(proxy)

        # Only want to include proxy if it is fundamentally different
        # than proxies we have already.
        differences = current.compare(proxy, return_difference=True)
        if differences:
            log.info(self, 'Updating Source Proxy in Pool',
                proxy, other=str(differences), source=source)

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
                log.info(self, f'Running Low on Proxies: {self.qsize()}')
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
                log.critical(self,
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

    async def _remove_proxy(self, proxy, invalid=False, reason=None, source=None):
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
