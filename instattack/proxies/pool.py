from __future__ import absolute_import

import heapq
import stopit
import itertools
from urllib.parse import urlparse

from proxybroker import ProxyPool

from instattack import MethodObj, settings
from instattack.data import read_proxies, write_proxies

from .exceptions import ProxyPoolException, PoolNoProxyError, BrokerNoProxyError
from .utils import filter_saved_proxies
from .models import RequestProxy


__all__ = ('CustomProxyPool', )

"""
Prioritization Notes

We should be looking at prioritizing proxies by `confirmed = True` where
the time since it was last used is above a threshold (if it caused a too
many requests error) and then look at metrics.

import heapq

data = [
    ((5, 1, 2), 'proxy1'),
    ((5, 2, 1), 'proxy2'),
    ((3, 1, 2), 'proxy3'),
    ((5, 1, 1), 'proxy5'),
]

heapq.heapify(data)
for item in data:
    print(item)

We will have to re-heapify whenever we go to get a proxy (hopefully not
too much processing) - if it is, we should limit the size of the proxy queue.

Priority can be something like (x), (max_resp_time), (error_rate), (times used)
x is determined if confirmed AND time since last used > x (binary)
y is determined if not confirmed and time since last used > x (binary)

Then we will always have prioritized by confirmed and available, not confirmed
but ready, all those not used yet... Might not need to prioritize by times
not used since that is guaranteed (at least should be) 0 after the first
two priorities
"""

"""
Priority Queue Example
A priority queue is common use for a heap, and it presents several implementation
challenges:

Sort stability: how do you get two tasks with equal priorities to be returned in
the order they were originally added?

Tuple comparison breaks for (priority, task) pairs if the priorities are equal
and the tasks do not have a default comparison order.

If the priority of a task changes, how do you move it to a new position in the
heap?

Or if a pending task needs to be deleted, how do you find it and remove it from
the queue?

A solution to the first two challenges is to store entries as 3-element list
including the priority, an entry count, and the task. The entry count serves as
a tie-breaker so that two tasks with the same priority are returned in the
order they were added. And since no two entry counts are the same, the tuple
comparison will never attempt to directly compare two tasks.

Another solution to the problem of non-comparable tasks is to create a wrapper
class that ignores the task item and only compares the priority field:

from dataclasses import dataclass, field
from typing import Any

@dataclass(order=True)
class PrioritizedItem:
    priority: int
    item: Any=field(compare=False)


The remaining challenges revolve around finding a pending task and making
changes to its priority or removing it entirely. Finding a task can be done
with a dictionary pointing to an entry in the queue.

Removing the entry or changing its priority is more difficult because it would
break the heap structure invariants. So, a possible solution is to mark the
ntry as removed and add a new entry with the revised priority:

pq = []                         # list of entries arranged in a heap
entry_finder = {}               # mapping of tasks to entries
REMOVED = '<removed-task>'      # placeholder for a removed task
counter = itertools.count()     # unique sequence count

def add_task(task, priority=0):
    'Add a new task or update the priority of an existing task'
    if task in entry_finder:
        remove_task(task)
    count = next(counter)
    entry = [priority, count, task]
    entry_finder[task] = entry
    heappush(pq, entry)

def remove_task(task):
    'Mark an existing task as REMOVED.  Raise KeyError if not found.'
    entry = entry_finder.pop(task)
    entry[-1] = REMOVED

def pop_task():
    'Remove and return the lowest priority task. Raise KeyError if empty.'
    while pq:
        priority, count, task = heappop(pq)
        if task is not REMOVED:
            del entry_finder[task]
            return task
    raise KeyError('pop from an empty priority queue')
"""

counter = itertools.count()


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
        proxies,
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
        read_proxy_list = []
        self.log.info('Prepopulating Proxy Pool')

        proxies = read_proxies(method=self.method)
        for proxy in filter_saved_proxies(
            proxies,
            max_error_rate=self._max_error_rate,
            max_resp_time=self._max_resp_time
        ):
            if proxy in read_proxy_list:
                # This isn't totally necessary since we check for duplicates
                # in the .put() method, but it helps us know where they
                # are coming from if we see them.
                self.log.warning('Found Duplicate Saved Proxy', extra={'proxy': proxy})
            else:
                read_proxy_list.append(proxy)
                await self.put(proxy)
        return read_proxy_list

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
            import ipdb; ipdb.set_trace()
            if prepopulate:
                await self.prepopulate(loop)

            while True:
                proxy = await self._broker._proxies.get()
                if proxy:
                    self.log.debug('Retrieved Proxy from Broker', extra={'proxy': proxy})
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
                        await self.put(proxy)
                else:
                    if not self._stopped:
                        self.log.debug('No More Proxies in Broker')
                        raise BrokerNoProxyError()
                    else:
                        # This block only gets reached after the self.put method is
                        # called with a proxy value of None, which triggers the self.stop()
                        # method.  That means that all we have to do here is exit
                        # the loop.
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

        # This might immediately raise no proxy error if there are none in the
        # pool yet.
        proxy = await self.pop_proxy()
        self.log.debug('Retrieving Proxy from Pool', extra={
            'proxy': proxy,
            'other': proxy.stat
        })
        return proxy

    async def put(self, proxy, priority=None):
        """
        Add a new proxy or udpate the priority of an existing proxy.
        """
        priority = priority or proxy.priority

        if proxy is None:
            # ProxyBroker package might actually put None in when there are no
            # more proxies in which case this can cause issues.
            self.log.warning(f"{self.__class__.__name__} is Stopping")
            await self.stop()
            return

        # This will reset num_requesets to 0 which is what we want.
        if not isinstance(proxy, RequestProxy):
            proxy = RequestProxy.from_proxybroker(proxy, self.method)

        valid = self.evaluate_proxy_before_insert(proxy)
        if not valid:
            # I don't think this should happen - but just in case, if the proxy
            # is no longer valid, we want to remove from the pool.  This might
            # happen for proxies where values change after use.

            # We might need to increment broker limit here.
            if proxy.address in self.proxy_finder:
                self.remove_proxy(proxy)
                self.log.warning('Removed Proxy from Pool', extra={'proxy': proxy})
            return

        if proxy.address in self.proxy_finder:
            self.log.warning('Removing Duplicate Proxy in Pool', extra={'proxy': proxy})
            self.remove_proxy(proxy)

        count = next(self.proxy_counter)
        entry = [priority, count, proxy]
        self.proxy_finder[proxy.address] = entry

        self.log.debug('Adding Proxy to Pool', extra={
            'proxy': proxy,
            'other': proxy.stat
        })
        heapq.heappush(self._pool, entry)

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
                        del self.proxy_finder[proxy.address]
                        return proxy
                    else:
                        self.log.debug('Popped Proxy was Removed')

        # We might want to raise an exception here to indicate that there
        # are no more proxies instead!
        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise PoolNoProxyError()

    def remove_proxy(self, proxy):
        """
        Mark an existing proxy as REMOVED.  Raise KeyError if not found.
        """
        entry = self.proxy_finder.pop(proxy.address)
        entry[-1] = self.REMOVED

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

    def save(self, overwrite=False):
        """
        Even though the _pool might contain prepoplulated proxies that were read
        from the text source, the write_proxies utility will only save the unique
        ones on top of the existing ones.
        """
        collected = []
        for [priority, count, proxy] in self._pool:
            if proxy is None:
                self.log.warning('Found Null Proxy While Saving...')
            else:
                collected.append(proxy)

        self.log.notice(f'Saving Proxies in Pool to {self.method.lower()}.txt.',
            extra={'other': f'Pool Size: {len(self._pool)}'})
        write_proxies(self.method, collected, overwrite=overwrite)
