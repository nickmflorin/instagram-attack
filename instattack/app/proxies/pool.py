import asyncio
import itertools

from instattack.config import config
from instattack.app.exceptions import PoolNoProxyError
from instattack.app.mixins import LoggerMixin

from .models import Proxy


"""
[!] IMPORTANT:
-------------

In the long run, it might be best to eventually separate into multiple queues,
for failed proxies, confirmed proxies and non confirmed proxies, pulling from
the desired queues based on priority.
"""


class ConfirmedQueue(asyncio.Queue, LoggerMixin):

    __name__ = 'Confirmed Queue'

    async def get(self):
        """
        Retrieves the oldest proxy from the queue but does not remove it from
        the queue.  This allows multiple threads access to the same proxy.
        """
        if self.qsize() != 0:
            return self.queue[0]

    async def put(self, proxy):
        """
        [x] Note:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the ConfirmedQueue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.
        """
        if proxy not in self.queue:
            await super(ConfirmedQueue, self).put(proxy)

    async def remove(self, proxy):
        """
        [x] Note:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time (not the case for HeldQueue), it is possible
        that the proxy is already removed from the ConfirmedQueue by the time another
        thread determines it should be removed.
        """
        if proxy in self.queue:
            self.queue.remove(proxy)


class HeldQueue(asyncio.Queue, LoggerMixin):

    __name__ = 'Held Queue'

    def __init__(self, limit, confirmed, pool):
        super(HeldQueue, self).__init__(limit)
        self.confirmed = confirmed
        self.pool = pool

    async def get(self):
        """
        Retrieves the first oldest proxy from the queue that should not be held
        anymore.
        """
        for proxy in self.queue:
            if not proxy.hold():
                # This prevents the simultaneous thread use.
                self.queue.remove(proxy)
                return proxy
        return None

    async def recycle(self):
        """
        Removes proxies from the hold that are no longer required to be in
        hold.  If the proxy has been confirmed to have a successful request, the
        proxy is put in good, otherwise, the proxy is put back in the pool.

        [x] TODO:
        --------
        Do we want to use active or historical num_requests to determine
        if the proxy should be put in the good queue or not?

        ^^ Probably not the most important matter, because the errors that cause
        a proxy to be put in hold usually mean that there was a success somewhere.
        """
        for proxy in self.queue:
            if proxy.hold():
                continue
            if proxy.is_confirmed():
                await self.confirmed.put(proxy)
            else:
                await self.pool.put(proxy, evaluate=False)

    async def put(self, proxy):
        """
        [x] Note:
        ---------
        Proxies in Hold Queue are not used by multiple threads simultaneously,
        so when one thread determines that the proxy should be put in the
        Hold Queue, it should not already be in there.
        """
        log = self.create_logger('add')

        if proxy not in self.queue:
            await super(HeldQueue, self).put(proxy)
        else:
            # This is Not a Race Condition
            await log.warning('Cannot Add Proxy to Hold Queue', extra={
                'other': 'Proxy Already in Hold Queue',
                'proxy': proxy,
            })

    async def remove(self, proxy):
        log = self.create_logger('remove')

        if proxy in self.queue:
            self.queue.remove(proxy)
        else:
            # This is Not a Race Condition
            await log.warning('Cannot Remove Proxy from Hold Queue', extra={
                'other': 'Proxy Not in Hold Queue',
                'proxy': proxy,
            })


class ProxyPool(asyncio.PriorityQueue, LoggerMixin):

    __name__ = 'Proxy Pool'

    def __init__(self, loop, broker, start_event=None):
        # We do not want to restrict the size of the Proxy Pool because it can
        # be detrimental for larger attack sizes.
        super(ProxyPool, self).__init__(-1)

        self.loop = loop

        self.broker = broker
        self.start_event = start_event
        self.timeout = config['pool']['timeout']

        # self.good_lock = asyncio.Lock()
        # self.hold_lock = asyncio.Lock()

        self.confirmed = ConfirmedQueue(-1)
        self.held = HeldQueue(-1, self.confirmed, self)

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()
        self.last_logged_qsize = None

    async def prepopulate(self):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        log = self.create_logger('prepopulate')
        await log.start('Prepopulating Proxies')

        proxy = await Proxy.get(id=1589)
        proxies = await Proxy.all()

        for proxy in proxies:
            if proxy.is_confirmed():
                await self.confirmed.put(proxy)
            else:
                evaluation = proxy.evaluate_for_pool()
                if evaluation.passed:
                    await self.put(proxy)

        if self.num_proxies == 0:
            await log.error('No Proxies to Prepopulate')
            return

        await log.complete(f"Prepopulated {self.num_proxies} Proxies")
        await log.complete(f"Prepopulated {self.confirmed.qsize()} Good Proxies")

    async def collect(self):
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

        count = 0
        collect_limit = 10000  # Arbitrarily high for now.

        async for proxy, created in self.broker.collect(save=True):
            evaluation = proxy.evaluate_for_pool()
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
        return self.qsize() + self.held.qsize() + self.confirmed.qsize()

    async def on_proxy_request_error(self, proxy, err):
        """
        Callback for case when request notices a request error.

        Always remove from Good Queue if present.

        Only remove from Hold Queue if the error is not consistent with errors
        that cause proxies to be put in Hold Queue.

        If proxy was just in the Hold Queue before error occured, and the error
        is the same, we should increment the timeout.

        [x] TODO:
        --------
        For the case of the pool (and not the login handler) the callbacks for
        request and response errors of the proxy are exactly the same, so these
        two methods can be consolidated.
        """
        proxy.num_requests += 1
        proxy.num_active_requests += 1
        proxy.last_request_confirmed = False

        if proxy in self.confirmed.queue:
            await self.confirmed.remove(proxy)

        # For errors that are related to just holding the proxy temporarily and
        # then returning, do not include in historical errors.
        if not err.__hold__:
            proxy.add_error(err)

            # Proxy evaluated in put() method, will be discarded if not valid.
            await self.put(proxy)

        else:
            # Increment timeout if we keep seeing the error.
            if proxy.last_active_error and proxy.last_active_error.__hold__:
                print(f'Warning: Incrementing Timeout Value due to {err.__subtype__}')
                proxy.increment_timeout(err.__subtype__)

            proxy.set_recent_error(err, historical=True, active=True)
            await self.held.put(proxy)

    async def on_proxy_response_error(self, proxy, err):
        """
        Callback for case when request notices a response error.

        Always remove from Good Queue if present.

        Only remove from Hold Queue if the error is not consistent with errors
        that cause proxies to be put in Hold Queue.

        If proxy was just in the Hold Queue before error occured, and the error
        is the same, we should increment the timeout.

        [x] TODO:
        --------
        For the case of the pool (and not the login handler) the callbacks for
        request and response errors of the proxy are exactly the same, so these
        two methods can be consolidated.
        """
        proxy.num_requests += 1
        proxy.num_active_requests += 1
        proxy.last_request_confirmed = False

        if proxy in self.confirmed.queue:
            await self.confirmed.remove(proxy)

        # For errors that are related to just holding the proxy temporarily and
        # then returning, do not include in historical errors.
        if not err.__hold__:
            proxy.add_error(err)

            # Proxy evaluated in put() method, will be discarded if not valid.
            await self.put(proxy)

        else:
            # Increment timeout if we keep seeing the error.
            if proxy.last_active_error and proxy.last_active_error.__hold__:
                print(f'Warning: Incrementing Timeout Value due to {err.__subtype__}')
                proxy.increment_timeout(err.__subtype__)

            proxy.set_recent_error(err, historical=True, active=True)
            await self.held.put(proxy)

    async def on_proxy_success(self, proxy):

        proxy.num_requests += 1
        proxy.num_active_requests += 1
        proxy.last_request_confirmed = True
        proxy.confirmed = True

        # There is a chance that the proxy is already in the good queue...
        if proxy not in self.confirmed.queue:
            await self.confirmed.put(proxy)

    async def get(self):
        """
        Remove and return the lowest priority proxy in the pool.

        Raise a PoolNoProxyError if it is taking too long.  We do not want to raise
        PoolNoProxyError if the queue is empty (and other sources are empty) since
        proxies actively being used may be momentarily put back in the queue or
        other sources.

        [!] IMPORTANT:
        -------------
        We need to figure out a way to trigger more proxies from being collected
        if we wind up running out of proxies - this might involve adjusting the
        timeout so it does not think there are no more proxies when they are just
        all currently being used.
        """
        log = self.create_logger('get')

        await self.held.recycle()

        if self.num_proxies <= 20:
            # Log Running Low on Proxies Periodically if Change Noticed
            if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                self.last_logged_qsize = self.num_proxies
                await log.warning(f'Running Low on Proxies: {self.num_proxies}')

        try:
            return await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()

    async def _get_proxy(self):
        """
        Good = [Proxy]
        Hold = [Proxy]
        Pool = queue(Proxy) (This object)

        Definition: Recycling Hold
        ----------
        Recycling the Hold means looking at the proxies in the structure and
        determining if any are ready to be used again.

        If they are ready to be used, confirmed proxies (ones that have a successful
        historical request) are moved to Good.  Unconfirmed proxies are put back
        in the pool.

        [!] Anytime a proxy is retrieved from Good or Hold, the Hold will be
        recycled.

        Case 1:
        ------
        Good is not empty, and thus we want to return a proxy from that structure
        but do not want to remove it from the structure so it can be used by other
        concurrent requests.

            -> Return Proxy from Good
            -> Recycle Proxies in Hold

            Outcomes:
            --------
            1. 429 Error:  Removed from Good and put in Hold.
            2. Non 429 Error: Removed from Good.  We reevaluate if it should stay
                              in pool, and either put in pool or discard.
            3. Valid Result:  Do nothing, it is still in good.

        Case 2:
        ------
        Good is empty, but Hold is not empty.  We want to remove the proxy from
        Hold to be used, and unlike in Case 1 with Good, we don't want other proxies
        to use concurrently (this is because the reason it is in hold is because
        of a 429 error.)

            -> Return Proxy from Hold
            -> Recycle Other Proxies in Hold

            Outcomes:
            --------
            1. 429 Error: We put back in hold and hope that it has time to sit
                          for a longer period of time.
            2. Non 429 Error: Removed from Good.  We reevaluate if it should stay
                              in pool, and either put in pool or discard.
            3. Valid Result:  Put proxy in Good

        Case 3:
        ------
        Good is empty AND Hold is empty.  We retrieve a proxy from the prioritized
        queue.

            -> Return Proxy from Prioritized Queue

            Outcomes:
            --------
            1. 429 Error: We put the proxy in Hold.
            2. Non 429 Error: Removed from Good.  We reevaluate if it should stay
                              in pool, and either put in pool or discard.
            3. Valid Result:  Put proxy in Good

        [!] Note:
        --------
        We might be able to avoid Case 2 if we always recycle the hold
        before Case 1, so that any available proxies that would be removed from
        hold are put in good.
        """
        while True:
            proxy = await self.confirmed.get()
            if proxy:
                return proxy

            proxy = await self.held.get()
            if proxy:
                return proxy

            ret = await super(ProxyPool, self).get()
            proxy = ret[1]

            # Proxies that should be held should be put in the Hold Queue and
            # only removed when they should not be held anymore.
            if proxy.hold() or proxy.is_confirmed():
                raise RuntimeError(
                    "There should not be held or confirmed proxies in queue.")

            # Proxies are always evaluated before being put in queue so we do
            # not have to reevaluate.
            return proxy

    async def put(self, proxy, evaluate=True):
        """
        Adds proxy to the pool and keeps record in proxy_finder for accessing
        at later point.

        [!] IMPORTANT:
        -------------
        Sometimes we might want to still add the proxy even if the
        quantitative metrics aren't perfect, but we know the proxy has
        successful requests -> Reason for Strict Parameter

        [!] IMPORTANT:
        -------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """
        if evaluate:
            evaluation = proxy.evaluate_for_pool()
            if not evaluation.passed:
                return

        count = next(self.proxy_counter)
        priority = proxy.priority(count)
        await super(ProxyPool, self).put((priority, proxy))
