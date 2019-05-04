from __future__ import absolute_import

import heapq
import stopit
import itertools
from urllib.parse import urlparse

from proxybroker import ProxyPool

from instattack import settings
from instattack.base import MethodObj
from instattack.models import RequestProxy
from instattack.mgmt.utils import read_proxies, write_proxies

from .exceptions import ProxyPoolException, PoolNoProxyError


__all__ = ('CustomProxyPool', )


# Temporary until we incorporate better logging, we don't want to clog the log
# with proxy updates.
LOG_PROXIES = True
LOG_SAVED_PROXIES = False


class CustomProxyPool(ProxyPool, MethodObj):
    """
    Imports and gives proxies from queue on demand.

    Overridden because of weird error referenced:

    Weird error from ProxyBroker that makes no sense...
    TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'

    We also want the ability to put None in the queue so that we can stop the
    consumers.
    """
    __subname__ = "Proxy Pool"
    REMOVED = '<removed-proxy>'

    def __init__(
        self,
        broker,
        method=None,
        timeout=None,
        min_req_proxy=None,
        max_error_rate=None,
        max_resp_time=None,
    ):
        self._broker = broker
        self._pool = []

        # Useful to keep track of which proxies were imported from .txt file.
        self._prepopulated = []

        self._max_error_rate = max_error_rate
        self._max_resp_time = max_resp_time
        self._min_req_proxy = min_req_proxy
        self._timeout = timeout

        # self._stopped is defined in the MethodObj.
        # We need to use this so that we can tell the difference when the found
        # proxy is None as being intentionally put in the queue to stop the
        # consumer or because there are no more proxies left from the Broker.

        self._setup(method=method)

        # The entry count serves as a tie-breaker so that two tasks with the
        # same priority are returned in the order they were added.
        # And since no two entry counts are the same, the tuple comparison will
        # never attempt to directly compare two tasks.
        self.proxy_counter = itertools.count()

        # Mapping of proxies to entries in the heapq
        self.proxy_finder = {}

    @property
    def scheme(self):
        scheme = urlparse(settings.URLS[self.method]).scheme
        return scheme.upper()

    @property
    def num_prepopulated(self):
        return len(self._prepopulated)

    @property
    def new_proxies(self):
        # Convenience for now, can't figure out why the number of new proxies
        # seems to always differ slightly from the proxy_limit.
        return [proxy[2] for proxy in self._pool if not proxy[2].saved]

    async def prepopulate(self, loop, lock):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.

        Pt. 1
        -----
        Checking for duplicates as we are reading isn't totally necessary, since
        they would be handled appropriately in the .put() method, but it is probably
        better to put in a clean set - and we can tell if there are save issues
        by checking duplicates here.
        """
        self.log.info('Prepopulating Proxy Pool')

        proxies = read_proxies(method=self.method)
        self.log.info(f"Read {len(proxies)} Proxies")

        for proxy in proxies:
            if proxy in self._prepopulated:
                # Pt. 1
                self.log.warning('Found Duplicate Saved Proxy', extra={'proxy': proxy})
            else:
                self._prepopulated.append(proxy)

                # Can't figure out if lock is what is causing problems when running
                # proxy handler with other handlers.
                async with lock:
                    await self.put(proxy)

        if self.num_prepopulated != 0:
            self.log.info(f"Prepopulated {self.num_prepopulated} Proxies")

            # Can't figure out if lock is what is causing problems when running
            # proxy handler with other handlers.
            async with lock:
                self.log.critical(f"Num in Pool {len(self._pool)}")
        else:
            self.log.error('No Proxies to Prepopulate')

    async def run(self, loop, lock, prepopulate=True):
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

        Pt. 3
        -----
        If the broker has been stopped and the value of the proxy is None, that
        means there are no more proxies to process and we want to stop the pool
        from continuing to process them.

            Stopping the pool inside this method probably isn't necessary, since
            it is stopped from the handler as well, but it will be faster since
            we won't get stuck in the middle of the block.
        """
        # async with self._start(loop):
        # Pt. 1
        if prepopulate:
            if self._prepopulated:
                raise ProxyPoolException("Pool was already prepopulated.")
            await self.prepopulate(loop, lock)

        # Pt. 2
        while not self._stopped:
            proxy = await self._broker._proxies.get()
            if proxy:
                proxy = RequestProxy.from_proxybroker(proxy, self.method)
                if self.scheme not in proxy.schemes:
                    # This should not be happening, but does sometimes with the
                    # proxybroker.
                    self._broker.increment_limit()
                    self.log.error('Expected Scheme not in Proxy Schemes', extra={
                        'proxy': proxy
                    })
                else:
                    async with lock:
                        await self.put(proxy)
            else:
                # Pt. 3
                if not self._broker._stopped:
                    raise ProxyPoolException("Proxy should not be null for running broker.")

                if not self._stopped:
                    # Used to raise BrokerNoProxyError()
                    await self.stop(loop)

    def sync_stop(self, loop):
        with self._sync_stop(loop):
            self._stopped = True

    async def stop(self, loop):
        """
        Prevents the pool from continuing to try to process proxies from the
        broker, but also leaves the pool available so that other handlers can
        access the proxies.
        """
        async with self._stop(loop):
            self._stopped = True

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
        # We might want to apply the lock more broadly? - Especially if things
        # start acting weirdly.
        with stopit.SignalTimeout(self._timeout) as timeout_mgr:
            self.log.debug('Waiting on Proxy from Pool')
            while True:
                if self._pool:

                    # We might need a lock here - haven't noticed issues yet.
                    priority, count, proxy = heapq.heappop(self._pool)

                    if proxy is not self.REMOVED:
                        if LOG_PROXIES:
                            self.log.debug('Retrieved Proxy from Pool', extra={
                                'proxy': proxy,
                                'other': f'Priority: {proxy.priority}'
                            })

                        del self.proxy_finder[proxy.id]
                        return proxy
                    else:
                        if LOG_PROXIES:
                            self.log.debug('Popped Proxy was Removed')

        # No more proxies in pool since timeout is sufficiently long.
        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise PoolNoProxyError()

    async def put(self, proxy):
        """
        Add a new proxy or udpate the priority of an existing proxy in the pool.

        Pt. (1)
        -------
        ProxyBroker package might actually put None in when there are no
        more proxies from the .find() method (i.e. it reaches the limit).  That
        means the pool has to stop.

        ** We need to look into this.  For handlers relying on the pool, like the
        TokenHandler, we might not want to stop the pool (since it sets the pool
        to _pool=[]), but just stop the broker. **

        Pt. (2)
        -------
        Makes sure that proxy is still valid according to what we require for
        metrics.  This can change after a proxy that was initially valid is used.
        ** TOO MANY REQUESTS **

        TODO:  We should maybe start storing a `valid` attribute on the proxy
               and filter by that value when we are retrieving?

        Pt. (3) Updating Proxy
        ----------------------
        This means whenever a proxy is used and put back in the queue, it's
        priority or other attributes will have changed, so it will be replaced.

        If we are updating the priority of a proxy in the queue, we cannot remove
        it completely because it would break the heapq invariants.  Instead,
        we mark it as removed and add the other proxy.

        Pt. (3a) Updating Proxy
        -----------------------
        Only want to update if the proxies are different.  Comparison excludes
        the value of the `saved` field.  We might want to restrict the fields
        we are looking at when calling `manage proxies collect`, since we don't
        need to update for slight variations to those metrics (they would be
        updated anyways when running live).

        Pt. (4) Adding New Proxy
        ------------------------
        Adds a proxy that we have not seen before to the _pool.
        """

        # Pt. (1)
        if proxy is None:
            self.log.warning(f"{self.__class__.__name__} is Stopping")
            await self.stop()
            return

        # This will reset num_requesets to 0 which is what we want.
        if not isinstance(proxy, RequestProxy):
            raise ProxyPoolException('Invalid proxy passed in, cannot put '
                'proxybroker proxies in pool.')

        # Pt. (2)
        valid, reason = proxy.evaluate(
            num_requests=self._min_req_proxy,
            error_rate=self._max_error_rate,
            resp_time=self._max_resp_time,
            scheme=self.scheme,
        )

        if not valid:
            self._broker.increment_limit()
            if proxy.id in self.proxy_finder:
                self._remove_proxy(proxy, invalid=True, reason=reason)
            else:
                self.log.warning('Cannot Add Proxy', extra={
                    'other': reason,
                    'proxy': proxy
                })

        else:
            # Pt. (3): Updating Proxy
            if proxy.id in self.proxy_finder:
                # Pt. (3a)
                current_entry = self.proxy_finder[proxy.id]
                current = current_entry[-1]
                if current != proxy:
                    differences = current.__diff__(proxy)
                    if differences.none:
                        raise ProxyPoolException('Proxies must have differences to update.')

                    # Make sure we maintain the proxy_limit value.
                    self._broker.increment_limit()

                    # Old proxy needs to be set to REMOVED
                    entry = self.proxy_finder[proxy.id]
                    self._update_proxy(entry[-1], proxy, differences)

            # Pt. (4): Adding New Proxy
            else:
                self._add_proxy(proxy)

    def notification(self, proxy, action='add', **kwargs):
        extra = {'proxy': proxy}
        extra.update(**kwargs)

        actions = {
            'add': 'Adding %{type}s Proxy to Pool',
            'update': 'Updating %{type}s Proxy in Pool',
        }

        msg = actions[action]
        if proxy.saved:
            return msg.format(type='Saved'), extra

        return msg.format(type='Broker'), extra

    def _add_proxy(self, proxy):
        """
        Adds proxy to the pool without disrupting the heapq invariant.

        Pt. (1) Using Count
        -------------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """

        # Pt. (1) Using Count
        count = next(self.proxy_counter)
        self.proxy_finder[proxy.id] = [proxy.priority, count, proxy]

        # Don't flood log
        if (proxy.saved and LOG_SAVED_PROXIES) or (not proxy.saved and LOG_PROXIES):
            notification = self.notification(proxy, action='add',
                other=f'Priority: {proxy.priority}')
            self.log.debug(notification)

        # Not an async function
        # async with self.lock:
        heapq.heappush(self._pool, [proxy.priority, count, proxy])

    def _remove_proxy(self, proxy, invalid=False, reason=None):
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

        # Only notify if we are removing a proxy because it was invalid, not
        # because it was being updated.
        extra = {'proxy': proxy}
        if invalid:
            reason = reason or "Unknown Reason"
            extra['other'] = reason
            self.log.warning('Removing Proxy from Pool', extra=extra)

        # Pt. (1) Marking as REMOVED
        entry = self.proxy_finder.pop(proxy.id)
        entry[-1] = self.REMOVED

    def _update_proxy(self, old_proxy, proxy, differences):
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
        if (proxy.saved and LOG_SAVED_PROXIES) or (not proxy.saved and LOG_PROXIES):
            notification = self.notification(proxy, action='update',
                other=str(differences))
            self.log.debug(notification)

        self._remove_proxy(old_proxy)

        # if old_proxy != self.REMOVED:
        #     proxy.saved = old_proxy.saved
        self._add_proxy(proxy)

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

    def save(self, overwrite=False):
        """
        Even though the _pool might contain prepoplulated proxies that were read
        from the text source, the write_proxies utility will only save the unique
        ones on top of the existing ones.
        """
        self.log.notice(
            f'Saving {len(self.new_proxies)} Proxies in Pool '
            f'to {self.method.lower()}.txt.',
            extra={'other': f'Pool Size: {len(self._pool)}'})
        write_proxies(self.method, self.new_proxies, overwrite=overwrite)
