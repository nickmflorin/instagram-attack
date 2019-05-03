from __future__ import absolute_import

import heapq
import stopit
import itertools
from urllib.parse import urlparse

from proxybroker import ProxyPool

from instattack import MethodObj, settings
from instattack.data import read_proxies, write_proxies

from .exceptions import ProxyPoolException, PoolNoProxyError, BrokerNoProxyError
from .models import RequestProxy


__all__ = ('CustomProxyPool', )


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

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        self.log.info('Prepopulating Proxy Pool')

        proxies = read_proxies(method=self.method)
        for proxy in proxies:
            if proxy.address in self.proxy_finder:
                # This isn't totally necessary since we check for duplicates
                # in the .put() method, but it helps us know where they
                # are coming from if we see them.
                self.log.warning('Found Duplicate Saved Proxy', extra={'proxy': proxy})
            else:
                await self.put(proxy)

    async def start(self, loop, prepopulate=True):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        If the proxy that is retrieved from the self._broker_proxies Queue is None,
        but self._stopped is set, that means it was intentionally put in to shut
        down this task.

        Otherwise, if the proxy is None and self._stopped is not set, than this
        indicates that the ProxyBroker has reached its limit, so we raise the
        NoProxyError.
        """
        async with self._start(loop):
            if prepopulate:
                self.log.info('Prepopulating Proxies')
                await self.prepopulate(loop)

            while True:
                proxy = await self._broker._proxies.get()
                if proxy:
                    proxy = RequestProxy.from_proxybroker(proxy, self.method)
                    if self.scheme not in proxy.schemes:
                        # This should not be happening, but does sometimes with the
                        # proxybroker.  We have to make sure to increment the broker
                        # limit if this does happen, so we still finish with the
                        # correct number of proxies in the pool.
                        self._broker.increment_limit()
                        self.log.error('Expected Scheme not in Proxy Schemes', extra={
                            'proxy': proxy
                        })
                    else:
                        # We might need to also look at the method?  This might not be
                        # unique enough.
                        if proxy.address in self.proxy_finder:
                            self._broker.increment_limit()
                            self.log.warning('Broker Returned Proxy Already Discovered',
                                extra={'proxy': proxy})
                            self.remove_proxy(proxy)
                        await self.put(proxy)
                else:
                    if not self._stopped:
                        raise BrokerNoProxyError()
                    else:
                        # This block only gets reached after the self.put method is
                        # called with a proxy value of None, which triggers the self.stop()
                        # method.  That means that all we have to do here is exit
                        # the loop.
                        self.log.debug('Breaking out of pool.')
                        break

    async def stop(self, loop, save=False, overwrite=False):
        # Context manager sets _stopped.
        async with self._stop(loop):
            # We might be able to ignore doing this or do this in the broker
            # itself.
            await self._broker._proxies.put(None)
            if save:
                self.save(overwrite=overwrite)
            self._pool = []

    async def get(self):
        """
        Retrieves a proxy from the prioritized heapq, which is populated in
        the .start() task concurrently with whatever handler is accessing this
        method.
        """
        if self._stopped:
            raise ProxyPoolException("Cannot get proxy from stopped pool.")

        proxy = await self.pop_proxy()
        self.log.debug('Retrieving Proxy from Pool', extra={
            'proxy': proxy,
            'other': f'Priority: {proxy.priority}'
        })
        return proxy

    async def put(self, proxy):
        """
        Add a new proxy or udpate the priority of an existing proxy.
        This means whenever a proxy is put back in the queue after it is used
        it's priority will most likely change, so it will be replaced.
        """
        if proxy is None:
            # ProxyBroker package might actually put None in when there are no
            # more proxies in which case this can cause issues.
            self.log.warning(f"{self.__class__.__name__} is Stopping")
            await self.stop()
            return

        # This will reset num_requesets to 0 which is what we want.
        if not isinstance(proxy, RequestProxy):
            raise ProxyPoolException('Invalid proxy passed in, cannot put '
                'proxybroker proxies in pool.')

        # This can happen if the proxy is no longer valid, (i.e. too many
        # requests).  We might be able to just store a valid attribute on th
        # proxy and filter by this value when we are retrieving.
        valid = self.evaluate_proxy_before_insert(proxy)
        if not valid:
            self._broker.increment_limit()
            if proxy.id in self.proxy_finder:
                self._remove_proxy(proxy, reason='invalid')
            return

        # If we are updating the priority of a proxy in the queue, we cannot remove
        # it completely because it would break the heapq invariants.  Instead,
        # we mark it as removed and add the other proxy.
        if proxy.id in self.proxy_finder:
            # Only want to update if the proxies are different, this excludes the
            # `saved` field.
            # We might want to restrict the fields we update when collecting proxies.
            current_entry = self.proxy_finder[proxy.id]
            current = current_entry[-1]
            if current != proxy:
                differences = current.__diff__(proxy)
                if differences.none:
                    raise ProxyPoolException('Proxies must have differences to update.')

                # Make sure we maintain the proxy_limit value.
                self._broker.increment_limit()

                # Old proxy is needed to maintain consistency in some values.
                entry = self.proxy_finder[proxy.id]
                self._update_proxy(entry[-1], proxy, differences)
        else:
            self._add_proxy(proxy)

    def _remove_proxy(self, proxy, reason=None):
        """
        Mark an existing proxy as REMOVED.  Raise KeyError if not found.
        This is necessary because in order to update a proxy priority in the
        queue, we cannot simply remove the entry from heqpq.

        Removing the entry or changing its priority is more difficult because
        it would break the heap structure invariants. So, a possible solution
        is to mark the existing entry as removed and add a new entry with the
        revised priority:
        """
        extra = {'proxy': proxy, 'other': 'Removing Proxy from Pool'}
        if reason == 'invalid':
            self.log.warning('Invalid Proxy', extra=extra)
        # Want to just notify of update.
        elif reason == 'update':
            pass

        entry = self.proxy_finder.pop(proxy.id)
        entry[-1] = self.REMOVED

    def _add_proxy(self, proxy):
        # Adds proxy to the pool without disrupting the heapq invariant.
        count = next(self.proxy_counter)
        self.proxy_finder[proxy.id] = [proxy.priority, count, proxy]

        # Don't flood log with prepopulated proxies.
        if not proxy.saved:
            self.log.debug('Adding Proxy to Pool', extra={
                'proxy': proxy,
                'other': f'Priority: {proxy.priority}'
            })
        heapq.heappush(self._pool, [proxy.priority, count, proxy])

    def _update_proxy(self, old_proxy, proxy, differences):
        # Don't flood log with prepopulated proxies.
        if not proxy.saved:
            # This is actually super useful information but it floods the log
            # right now.
            self.log.debug('Updating Proxy in Pool', extra={
                'proxy': proxy,
                'other': str(differences),
            })
        # Shouldn't matter if we remove old
        self._remove_proxy(old_proxy, reason='update')

        # Some properties that we want to maintain.
        # Not sure if we want to do this anymore.
        # if old_proxy != self.REMOVED:
        #     proxy.saved = old_proxy.saved
        self._add_proxy(proxy)

    async def pop_proxy(self):
        """
        Remove and return the lowest priority proxy.
        Raise KeyError if empty.
        """

        # The timeout value needs to be large enough so that the Broker can spin
        # up and start populating the pool.  However, we probably want to find
        # a way to shorten it after the pool is populated, so we are not waiting
        # forever with an empty pool.
        with stopit.SignalTimeout(self._timeout) as timeout_mgr:
            self.log.debug('Waiting on Proxy from Pool')
            while True:
                if self._pool:
                    # We might need a lock here.
                    priority, count, proxy = heapq.heappop(self._pool)
                    if proxy is not self.REMOVED:
                        self.log.debug('Popped Proxy from Pool', extra={
                            'proxy': proxy,
                        })
                        # We might need a lock here.
                        del self.proxy_finder[proxy.id]
                        return proxy
                    else:
                        self.log.debug('Popped Proxy was Removed')

        # We might want to raise an exception here to indicate that there
        # are no more proxies instead!
        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise PoolNoProxyError()

    def evaluate_proxy_before_insert(self, proxy):
        """
        Evaluates whether or not conditions are met for a given proxy before
        it is inserted into the Queue.

        We might want to start min_req_per_proxy to a higher level since we
        are controlling how often they are used to avoid max request errors!!!

        We can also prioritize by number of requests to avoid max request errors
        """
        if proxy.num_requests >= self._min_req_proxy:
            self.log.warning('Discarding Proxy; Num Requests '
                f'{proxy.num_requests} > {self._min_req_proxy}',
                extra={'proxy': proxy})
            return False
        elif proxy.error_rate > self._max_error_rate:
            self.log.warning(f'Discarding Proxy; Error Rate '
                f'{proxy.error_rate} > {self._max_error_rate}',
                extra={'proxy': proxy})
            return False
        elif proxy.avg_resp_time > self._max_resp_time:
            self.log.warning(f'Discarding Proxy; Resp Time '
                f'{proxy.avg_resp_time} > {self._max_resp_time}',
                extra={'proxy': proxy})
            return False
        elif self.scheme not in proxy.schemes:
            self.log.warning(f'Discarding Proxy; Scheme {self.scheme} Not Supported',
                extra={'proxy': proxy})
            return False
        return True

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

    @property
    def new_proxies(self):
        # Convenience for now, can't figure out why the number of new proxies
        # seems to always differ slightly from the proxy_limit.
        return [proxy[2] for proxy in self._pool if not proxy[2].saved]

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
