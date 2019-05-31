import asyncio
import collections
import itertools

from instattack.app.exceptions import PoolNoProxyError
from instattack.app.mixins import LoggerMixin

from .models import Proxy
from .utils import stream_proxies


"""
[!] IMPORTANT:
-------------

In the long run, it might be best to eventually separate into multiple queues,
for failed proxies, confirmed proxies and non confirmed proxies, pulling from
the desired queues based on priority.
"""


class ProxyPool(asyncio.PriorityQueue, LoggerMixin):

    __name__ = 'Proxy Pool'

    def __init__(self, loop, broker, start_event=None):
        # We do not want to restrict the size of the Proxy Pool because it can
        # be detrimental for larger attack sizes.
        super(ProxyPool, self).__init__(-1)

        self.loop = loop
        self.config = self.loop.config

        self.broker = broker
        self.start_event = start_event
        self.timeout = self.config['instattack']['proxies']['pool']['timeout']

        self.lock = asyncio.Lock()

        self.hold = collections.deque()
        self.good = collections.deque()

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
            # We probably don't want to discard confirmed proxies because of
            # evaluation, right?
            proxy.reset()

            if proxy.last_request_confirmed:
                evaluation = proxy.evaluate_for_pool(self.config)
                if not evaluation.passed:
                    await log.warning('Confirmed Proxy Failed Validation... Still Putting In',
                        extra={
                            'other': str(evaluation)
                        }
                    )
                self.good.append(proxy)
            else:
                evaluation = proxy.evaluate_for_pool(self.config)
                if evaluation.passed:
                    await self.put(proxy)

        if self.num_proxies == 0:
            await log.error('No Proxies to Prepopulate')
            return

        await log.complete(f"Prepopulated {self.num_proxies} Proxies")
        await log.complete(f"Prepopulated {len(self.good)} Good Proxies")

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
            evaluation = proxy.evaluate_for_pool(self.config)
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
        return self.qsize() + len(self.hold) + len(self.good)

    async def on_proxy_request_error(self, proxy, err):

        proxy.num_requests += 1
        proxy.last_request_confirmed = False

        if proxy in self.good:
            async with self.lock:
                print('Removing Proxy from Good: %s' % err.__class__.__name__)
                self.good.remove(proxy)

        # For errors that are related to just holding the proxy temporarily and
        # then returning, do not include in historical errors.
        if err.__partial__:
            proxy.set_recent_error(err, historical=True, active=True)
            async with self.lock:
                # THIS IS NOT A RACE CONDITION
                # SEE INFO IN check_and_put
                if proxy not in self.hold:
                    print('Holding Proxy: %s' % err.__class__.__name__)
                    self.hold.append(proxy)
        else:
            proxy.add_error(err, historical=True, active=True, recent=True)

        await self.check_and_put(proxy)

    async def on_proxy_response_error(self, proxy, err):

        if proxy in self.good:
            async with self.lock:
                print('Removing Proxy from Good: %s' % err.__class__.__name__)
                self.good.remove(proxy)

        # For errors that are related to just holding the proxy temporarily and
        # then returning, do not include in historical errors.
        if err.__partial__:
            proxy.set_recent_error(err, historical=True, active=True)
            async with self.lock:
                # THIS IS NOT A RACE CONDITION
                # SEE INFO IN check_and_put
                if proxy not in self.hold:
                    print('Holding Proxy: %s' % err.__class__.__name__)
                    self.hold.append(proxy)
        else:
            proxy.add_error(err, historical=True, active=True, recent=True)

        proxy.num_requests += 1
        proxy.last_request_confirmed = False

        await self.check_and_put(proxy)

    async def on_proxy_success(self, proxy):
        proxy.num_requests += 1
        proxy.last_request_confirmed = True

        # Proxy will not be in hold since we pull out of hold, not copy out of
        # hold.
        self.good.append(proxy)

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

        if self.num_proxies <= 20:
            # Log Running Low on Proxies Periodically if Change Noticed
            if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                self.last_logged_qsize = self.num_proxies
                await log.warning(f'Running Low on Proxies: {self.num_proxies}')

        try:
            return await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()

    async def _recycle_hold(self):
        """
        Removes proxies from the hold that are no longer required to be in
        hold.  If the proxy has been confirmed to have a successful request, the
        proxy is put in good, otherwise, the proxy is put back in the pool.
        """
        for proxy in self.hold:
            if not proxy.hold(self.config):
                # Do we want to use active or historical?
                if proxy._num_requests(active=True, success=True) != 0:
                    if proxy in self.good:
                        raise RuntimeError('Proxy Already in Good')

                    async with self.lock:
                        print('Recycling Proxy from Hold to Good')
                        self.good.append(proxy)
                        self.hold.remove(proxy)
                else:
                    # Do we need to use check_and_put() here?
                    await self.put(proxy)

    async def _get_from_hold(self):
        for proxy in self.hold:
            hold = proxy.hold(self.config)
            if not hold:
                self.hold.remove(proxy)
                return proxy

    async def _get_from_good(self):
        """
        [!] Note:
        --------
        We might be able to avoid Case 2 if we always recycle the hold
        before Case 1, so that any available proxies that would be removed from
        hold are put in good.

        That might slow down things though since we would have to wait for the
        completion of self._recycle_hold().
        """
        if len(self.good) != 0:
            return self.good[0]

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
        loop = asyncio.get_event_loop()

        while True:
            # Not 100% sure if we have to check
            # >>> proxy.evaluate_for_use(self.config)
            proxy = await self._get_from_good()
            if proxy:
                # log.info('Returning Proxy from Good Proxies : %s' % len(self.good))
                loop.call_soon(self._recycle_hold())
                return proxy

            # Not 100% sure if we have to check
            # >>> proxy.evaluate_for_use(self.config)
            proxy = await self._get_from_hold()
            if proxy:
                print('Returning Proxy from Held Proxies : %s' % len(self.hold))
                loop.call_soon(self._recycle_hold())
                return proxy

            ret = await super(ProxyPool, self).get()
            proxy = ret[1]

            evaluation = proxy.evaluate_for_use(self.config)
            if evaluation.passed:
                return proxy

    async def check_and_put(self, proxy):
        """
        [!] IMPORTANT:
        -------------
        Sometimes we might want to still add the proxy even if the
        quantitative metrics aren't perfect, but we know the proxy has
        successful requests -> Reason for Strict Parameter

        [x] TODO:
        --------
        Another option to the .hold() methodology might be to have a confirmed
        queue and an unconfirmed queue, where the priority for the confirmed
        queue emphasizes only time since used, which is not a priority value of
        the unconfirmed queue.
        """
        log = self.create_logger('get')

        evaluation = proxy.evaluate_for_pool(self.config)
        if evaluation.passed:
            # We might not need this since we are putting proxies in hold up in
            # the handlers?  Although we do not check if we need to hold proxy...
            # This is why we are getting duplicates in the held proxies
            # if proxy.hold(self.config):
            #     async with self.lock:
            #         print('Holding Proxy')
            #         await log.debug('Putting Proxy in Hold')
            #         self.hold.append(proxy)
            # else:
                await self.put(proxy)
        else:
            log.debug('Discarding Proxy')

    async def put(self, proxy):
        """
        Adds proxy to the pool and keeps record in proxy_finder for accessing
        at later point.

        [!] IMPORTANT:
        -------------
        Tuple comparison for priority in Python3 breaks if two tuples are the
        same, so we have to use a counter to guarantee that no two tuples are
        the same and priority will be given to proxies placed first.
        """
        count = next(self.proxy_counter)
        priority = proxy.priority(count, self.config)
        await super(ProxyPool, self).put((priority, proxy))
        return proxy
