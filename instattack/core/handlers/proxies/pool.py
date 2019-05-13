import asyncio
import heapq
import itertools

from proxybroker import ProxyPool

from instattack.lib import starting
from instattack.exceptions import PoolNoProxyError, ArgumentError

from instattack.core.models import Proxy
from instattack.core.utils import stream_proxies, update_or_create_proxies
from instattack.core.handlers.base import MethodHandlerMixin


class CustomProxyPool(ProxyPool, MethodHandlerMixin):
    """
    Imports and gives proxies from queue on demand.

    Overridden because of weird error referenced:

    Weird error from ProxyBroker that makes no sense...
    TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'

    We also want the ability to put None in the queue so that we can stop the
    consumers.
    """
    __name__ = "Proxy Pool"
    REMOVED = '<removed-proxy>'

    def __init__(self, proxies, broker, config=None, **kwargs):
        self.engage(**kwargs)

        self.pool = []

        self.broker = broker
        self.broker_proxies = proxies  # Proxies from Broker

        self.log_proxies = config['log_proxies']

        self.max_error_rate = config['max_error_rate']
        self.max_resp_time = config['max_resp_time']
        self.min_req_proxy = config['min_req_proxy']
        self.timeout = config['timeout']

        self.collect = config['collect']
        self.prepopulate = config['prepopulate']

        self.limit = config['limit']
        self.prepopulate_limit = config['prepopulate_limit']
        if self.prepopulate_limit and self.prepopulate_limit >= self.limit:
            raise ArgumentError('Prepopulate limit must be less than the pool limit.')

        # The entry count serves as a tie-breaker so that two tasks with the
        # same priority are returned in the order they were added.
        # And since no two entry counts are the same, the tuple comparison will
        # never attempt to directly compare two tasks.
        self.proxy_counter = itertools.count()

        # Mapping of proxies to entries in the heapq
        self.proxy_finder = {}

    async def save(self, loop):
        """
        TODO
        ----
        We might want to not include the prepopulated proxies in here.  When
        collecting proxies, we don't prepopulate so that is not an issue, but
        if we are attacking, the prepopulated proxies will be in the pool
        (although this might be okay, since we will be updating their stats
        in the database).
        """
        proxies = []
        async with self.lock:
            proxies = [proxy[2] for proxy in self.pool]

        if len(proxies) == 0:
            self.log.error('No Proxies to Save')
            return

        await update_or_create_proxies(self.__method__, proxies)

    @starting
    async def run(self, loop):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.

        TODO:
        ----
        We should only run the proxybroker version if there are not enough
        proxies that are from prepopulation, because it can slow things down.  For
        GET requests, we should maybe limit the pool size to something like 20.
        """
        if self.prepopulate:
            await self.prepopulate_proxies(loop)

        self.start_event.set()
        if self.collect:
            await self.collect_proxies(loop)

    async def evaluate_proxy(self, proxy):
        """
        Makes sure that proxy is still valid according to what we require for
        metrics.  This can change after a proxy that was initially valid is used.
        **TOO MANY REQUESTS**
        """
        return proxy.evaluate(
            num_requests=self.min_req_proxy,
            error_rate=self.max_error_rate,
            resp_time=self.max_resp_time,
            # Trying to figure out what's going on with SSL error.
            # scheme=self.scheme,
        )

    @starting('Proxy Prepopulation')
    async def prepopulate_proxies(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.

        NOTE:
        ----
        Unlike the broker case, we can't run the loop/generator while
            >>> len(futures) <= some limit

        So we don't pass the limit into stream_proxies and only add futures if
        the limit is not reached.
        """
        futures = []
        async for proxy in stream_proxies(method=self.__method__):
            if not self.prepopulate_limit or len(futures) < self.prepopulate_limit:
                valid, reason = await self.evaluate_proxy(proxy)
                if valid:
                    futures.append(asyncio.create_task(self.put(proxy)))
                else:
                    self.log.warning('Cannot Add Saved Proxy to Pool', extra={
                        'proxy': proxy,
                        'other': reason,
                    })

        # Assumes there were no errors adding proxies, which might not be the
        # case.
        await asyncio.gather(*futures)
        if len(futures) != 0:
            self.log.complete(f"Prepopulated {len(futures)} Proxies")
        else:
            self.log.warning('No Proxies to Prepopulate')

    @starting('Proxy Collection')
    async def collect_proxies(self, loop):
        """
        Retrieves proxies from the broker and converts them to our Proxy model.
        The proxy is then evaluated as to whether or not it meets the standards
        specified and conditionally added to the pool.

        NOTE:
        ----
        The proxy returned from the broker should never be null (outside of edge
        cases) - the broker should only return a null proxy when it's limit is
        reached, and the limit is intentionally set much higher than the pool
        limit.

        TODO:
        ----
        We should maybe make this more dynamic, and add proxies from the broker
        when the pool drops below the limit.
        """
        num_prepopoulated = len(self.pool)
        num_to_collect = self.limit - num_prepopoulated

        futures = []
        while len(futures) < num_to_collect:
            proxy = await self.broker_proxies.get()
            if not proxy:
                raise RuntimeError('Broker should not return null proxy.')

            proxy = await Proxy.from_proxybroker(proxy, self.__method__)
            valid, reason = await self.evaluate_proxy(proxy)
            if valid:
                if self.log_proxies:
                    self.log.info('Found Proxy from Broker', extra={'proxy': proxy})
                futures.append(asyncio.create_task(self.put(proxy)))
            else:
                self.log.warning('Cannot Add Broker Proxy to Pool', extra={
                    'proxy': proxy,
                    'other': reason,
                })

        await asyncio.gather(*futures)

        # Note that if we are going to dynamically add back to the pool, we cannot
        # do this.
        # This might also cause issues since we do stop the broker from the
        # proxy handler stop method as well.
        self.broker.stop(loop)

    async def get(self):
        """
        Remove and return the lowest priority proxy in the pool.
        Raise KeyError if empty.

        The timeout value needs to be large enough so that the Broker can spin
        up and start populating the pool.  However, we probably want to find
        a way to shorten it after the pool is populated, so we are not waiting
        forever with an empty pool.

        Important:
        ---------
        Do not restrict the .get() method to cases when the pool is not stopped,
        we want the pool to be able to stop - which means stop processing proxies
        from the broker - but still leave the proxies in the pool retrievable
        for handlers that use it.

        TODO:
        ----
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
            proxy = await asyncio.wait_for(self._get(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()
        else:
            return proxy

    async def _get(self):
        while True:
            priority, count, proxy = None, None, None
            async with self.lock:
                if self.pool:
                    priority, count, proxy = heapq.heappop(self.pool)

            if proxy:
                if proxy is not self.REMOVED:
                    del self.proxy_finder[proxy.unique_id]
                    # self.log.debug('Removed Proxy from Pool', extra={'proxy': proxy})
                    return proxy

    async def put(self, proxy):
        """
        Add a new proxy or udpate the priority of an existing proxy in the pool.

        TODO:
        ----
        Should we maybe start saving proxies regardless of whether or not
        they are valid?  Or maybe just valid up to a certain extent?

        Since new proxies will not have an `id`, we can either save those
        proxies when they are created, of we can use another value to indicate
        the uniqueness of the proxy.
        """
        if not isinstance(proxy, Proxy):
            raise RuntimeError('Invalid proxy passed in.')

        # Updating Proxy
        if proxy.unique_id in self.proxy_finder:

            current_entry = self.proxy_finder[proxy.unique_id]
            current = current_entry[-1]

            # Only want to update if the proxies are different.
            differences = current.compare(proxy, return_difference=True)
            if differences:
                # Make sure we maintain the proxy_limit value.
                # We have no way of doing this anymore, we should maybe return
                # a result to say if it was put in the queue or not.
                # self._broker.increment_limit()

                # Old proxy needs to be set to REMOVED
                entry = self.proxy_finder[proxy.unique_id]
                await self._update_proxy(entry[-1], proxy, differences)

        # Adds a proxy that we have not seen before to the _pool.
        else:
            await self._add_proxy(proxy)

    async def _add_proxy(self, proxy):
        """
        Adds proxy to the pool without disrupting the heapq invariant.
        """

        # Tuple comparison for priority in Python3 breaks if two tuples are the
        # same, so we have to use a counter to guarantee that no two tuples are
        # the same and priority will be given to proxies placed first.
        count = next(self.proxy_counter)
        self.proxy_finder[proxy.unique_id] = [proxy.priority, count, proxy]

        async with self.lock:
            heapq.heappush(self.pool, [proxy.priority, count, proxy])

        # Do not log prepopulated proxies.
        if not proxy.id or self.log_proxies:
            self.log.debug('Added Proxy to Pool', extra={'proxy': proxy})

    async def _remove_proxy(self, proxy, invalid=False, reason=None):
        """
        Mark an existing proxy as REMOVED. Raise KeyError if not found.

        Marking as REMOVED is necessary because in order to update a proxy
        priority in the queue, this is because we cannot simply update or remove
        the entry from heqpq - it will upset the invariant.

        Solution is to mark the existing entry as removed and add a new entry
        with the revised priority:
        """
        entry = self.proxy_finder.pop(proxy.unique_id)
        entry[-1] = self.REMOVED

        # Only notify if we are removing a proxy because it was invalid, not
        # because it was being updated.
        if invalid:
            self.log.debug('Removed Proxy from Pool', extra={
                'proxy': proxy,
                'other': reason,
            })

    async def _update_proxy(self, old_proxy, proxy, differences):
        """
        Updates a proxy in the pool by first marking the original proxy as
        REMOVED and then adding the new proxy.  See notes in _remove_proxy()
        for explanation of why we set REMOVED instead of updating existing
        proxy in pool.
        """
        await self._remove_proxy(old_proxy)
        await self._add_proxy(proxy)

        # This is actually super useful information but it might flood the log,
        # we might disable until we have better logging system.
        self.log.debug('Updated Proxy in Pool', extra={
            'proxy': proxy,
            'other': str(differences),
        })
