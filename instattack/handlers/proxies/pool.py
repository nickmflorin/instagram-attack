import asyncio
import heapq
import itertools
from urllib.parse import urlparse

from proxybroker import ProxyPool

from instattack import settings
from instattack.models import Proxy
from instattack.handlers.control import Control
from instattack.exceptions import ProxyPoolException, PoolNoProxyError

from .utils import stream_proxies, update_or_create_proxies


class CustomProxyPool(ProxyPool, Control):
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

    def __init__(
        self,
        proxies,
        broker,
        timeout=None,
        min_req_proxy=None,
        max_error_rate=None,
        max_resp_time=None,
        **kwargs,
    ):
        self.engage(**kwargs)

        self._pool = []

        self._broker = broker
        self._broker_proxies = proxies  # Proxies from Broker

        # Useful to keep track of which proxies were imported from .txt file.
        self._prepopulated = []

        self._max_error_rate = max_error_rate
        self._max_resp_time = max_resp_time
        self._min_req_proxy = min_req_proxy
        self._timeout = timeout

        # The entry count serves as a tie-breaker so that two tasks with the
        # same priority are returned in the order they were added.
        # And since no two entry counts are the same, the tuple comparison will
        # never attempt to directly compare two tasks.
        self.proxy_counter = itertools.count()

        # Mapping of proxies to entries in the heapq
        self.proxy_finder = {}

    @property
    def scheme(self):
        scheme = urlparse(settings.URLS[self.__method__]).scheme
        return scheme.upper()

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        self.log.info('Prepopulating Proxy Pool')

        num_prepopulated = []
        async for proxy in stream_proxies(method=self.__method__):
            num_prepopulated.append(proxy)
            await self.put(proxy)

        if len(num_prepopulated) != 0:
            self.log.info(f"Prepopulated {len(num_prepopulated)} Proxies")
        else:
            self.log.error('No Proxies to Prepopulate')

    async def run(self, loop, prepopulate=True, save=False, overwrite=False):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Pt. 1
        -----
        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.

        Pt. 2
        -----
        Run until the broker stops sending proxies, in which case we will
        stop processing them, but the pool proxies can still be accessed.

        If the broker returns a proxy will a value of None, that means there are
        no more to find (we reached the limit) and we want to stop the pool
        from continuing to process them.

        Note that this does NOT mean the value of _pool will be reset to [], we
        still need those.

        TODO:
        ----
        Are there ever cases where we might want to save proxies on the fly?
        Then use the PK instead of the unique_id field?
        """
        if prepopulate:
            if self._prepopulated:
                raise ProxyPoolException("Pool was already prepopulated.")
            await self.prepopulate(loop)

        self.start_event.set()

        def proxy_in_pool(fut):
            if not fut.exception():
                # Might not want to log this forever, since it can clutter,
                # at least until we have better logging/display system.
                self.log.debug(f"Proxy Pool Size: {len(self._pool)}")
            else:
                self.log.error(fut.exception())

        async with self.starting(loop):
            tasks = []
            while True:
                proxy = await self._broker_proxies.get()
                if proxy:
                    # Right now, we are not saving the proxies until the end, since
                    # it will slow down the live operation.
                    proxy = await Proxy.from_proxybroker(proxy, self.__method__, save=False)
                    if self.scheme not in proxy.schemes:
                        # This should not be happening, but does sometimes with the
                        # proxybroker.
                        self._broker.increment_limit()
                        self.log.error('Expected Scheme not in Proxy Schemes', extra={
                            'proxy': proxy
                        })
                    else:
                        task = asyncio.create_task(self.put(proxy))
                        task.add_done_callback(proxy_in_pool)
                        tasks.append(task)
                else:
                    # Pt. 3
                    break

            await asyncio.gather(*tasks)
            if save:
                await self.save(overwrite=overwrite)

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
            proxy = await asyncio.wait_for(self._get(), timeout=self._timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()
        else:
            return proxy

    async def _get(self):
        while True:
            priority, count, proxy = None, None, None
            async with self.lock:
                if self._pool:
                    # We might need a lock here - haven't noticed issues yet.
                    priority, count, proxy = heapq.heappop(self._pool)

            if proxy:
                if proxy is not self.REMOVED:
                    del self.proxy_finder[proxy.unique_id]
                    self.log.debug('Removed Proxy from Pool', extra={'proxy': proxy})
                    return proxy

    async def put(self, proxy):
        """
        Add a new proxy or udpate the priority of an existing proxy in the pool.

        Pt. (1)
        -------
        Makes sure that proxy is still valid according to what we require for
        metrics.  This can change after a proxy that was initially valid is used.
        ** TOO MANY REQUESTS **

        TODO:  We should maybe start storing a `valid` attribute on the proxy
               and filter by that value when we are retrieving?

        Pt. (2)
        -------
        Updating Proxy

        This means whenever a proxy is used and put back in the queue, it's
        priority or other attributes will have changed, so it will be replaced.

        If we are updating the priority of a proxy in the queue, we cannot remove
        it completely because it would break the heapq invariants.  Instead,
        we mark it as removed and add the other proxy.

        Pt. (2a):
        ---------
        Updating Proxy

        Only want to update if the proxies are different.  Comparison excludes
        the value of the `saved` field.  We might want to restrict the fields
        we are looking at when calling `manage proxies collect`, since we don't
        need to update for slight variations to those metrics (they would be
        updated anyways when running live).

        Pt. (3):
        --------
        Adding New Proxy
        Adds a proxy that we have not seen before to the _pool.

        TODO:
        ----
        Should we maybe start saving proxies regardless of whether or not
        they are valid?  Or maybe just valid up to a certain extent?

        Since new proxies will not have an `id`, we can either save those
        proxies when they are created, of we can use another value to indicate
        the uniqueness of the proxy.
        """

        # This will reset num_requesets to 0 which is what we want.
        if not isinstance(proxy, Proxy):
            raise RuntimeError('Invalid proxy passed in.')

        # Pt. (1)
        valid, reason = proxy.evaluate(
            num_requests=self._min_req_proxy,
            error_rate=self._max_error_rate,
            resp_time=self._max_resp_time,
            scheme=self.scheme,
        )

        if not valid:
            self._broker.increment_limit()
            if proxy.unique_id in self.proxy_finder:
                await self._remove_proxy(proxy, invalid=True, reason=reason)
            else:
                self.log.warning('Cannot Add Proxy to Pool', extra={
                    'proxy': proxy,
                    'other': reason,
                })
            return

        # Pt. (2): Updating Proxy
        if proxy.unique_id in self.proxy_finder:

            # Pt. (2a)
            current_entry = self.proxy_finder[proxy.unique_id]
            current = current_entry[-1]
            if current != proxy:

                differences = current.__diff__(proxy)
                if differences.none:
                    raise RuntimeError('Proxies must have differences to update.')

                # Make sure we maintain the proxy_limit value.
                self._broker.increment_limit()

                # Old proxy needs to be set to REMOVED
                entry = self.proxy_finder[proxy.unique_id]
                await self._update_proxy(entry[-1], proxy, differences)

        # Pt. (3): Adding New Proxy
        else:
            await self._add_proxy(proxy)

    async def _add_proxy(self, proxy):
        """
        Adds proxy to the pool without disrupting the heapq invariant.

        Pt. (1)
        -------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """

        # Pt. (1) Using Count
        count = next(self.proxy_counter)
        self.proxy_finder[proxy.unique_id] = [proxy.priority, count, proxy]

        async with self.lock:
            heapq.heappush(self._pool, [proxy.priority, count, proxy])

        self.log.debug('Added Proxy to Pool', extra={'proxy': proxy})

    async def _remove_proxy(self, proxy, invalid=False, reason=None):
        """
        Mark an existing proxy as REMOVED.
        Raise KeyError if not found.

        Pt. (1) Marking as REMOVED
        --------------------------
        Marking as REMOVED is necessary because in order to update a proxy
        priority in the queue, this is because we cannot simply update or remove
        the entry from heqpq - it will upset the invariant.

        Solution is to mark the existing entry as removed and add a new entry
        with the revised priority:
        """

        # Pt. (1) Marking as REMOVED
        entry = self.proxy_finder.pop(proxy.unique_id)
        entry[-1] = self.REMOVED

        # Only notify if we are removing a proxy because it was invalid, not
        # because it was being updated.
        if invalid:
            self.log.warning('Removed Proxy from Pool', extra={
                'proxy': proxy,
                'other': reason,
            })

    async def _update_proxy(self, old_proxy, proxy, differences):
        """
        Updates a proxy in the pool by first marking the original proxy as
        REMOVED and then adding the new proxy.  See notes in _remove_proxy()
        for explanation of why we set REMOVED instead of updating existing
        proxy in pool.

        TODO
        ----
        We might not need to maintain consistency in the saved property, figure
        out if this matters or not.
        """
        # This is actually super useful information but it floods the log
        # right now - need better logging system to always monitor this.
        await self._remove_proxy(old_proxy)
        await self._add_proxy(proxy)

        self.log.warning('Updated Proxy in Pool', extra={
            'proxy': proxy,
            'other': str(differences),
        })

    # Not currently used, will factor into how we handle the priority of the proxies.
    def evaluate_proxy_before_retrieval(self, proxy):
        """
        Not currently used - but we are going to have to somehow incorporate checks
        into the proxy that we want to perform before returning from the heapq,
        or possibly build into the priority of the heapq.

        If we do it outside the context of the Proxy.priority value, this should
        also ensure that evaluate_proxy_before_insert() is still called, since those
        values are dynamic and will change over time.
        """
        # This needs to indicate that we still want to put it in the queue but
        # we do not want to use it yet.
        if proxy.last_used and proxy.time_since_used < 10:
            return False

        return True

    async def save(self, overwrite=False):
        """
        TODO
        ----
        We might want to not include the prepopulated proxies in here.
        """
        proxies = []
        async with self.lock:
            proxies = [proxy[2] for proxy in self._pool]

        # Not currently supporting overwrite.
        await update_or_create_proxies(self.__method__, proxies, overwrite=overwrite)