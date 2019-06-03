import asyncio
import itertools

from instattack.config import config

from instattack.app.exceptions import PoolNoProxyError
from instattack.app.mixins import LoggerMixin
from instattack.app.models import Proxy

from .queues import ConfirmedQueue, HeldQueue


__all__ = (
    'SimpleProxyPool',
    'BrokeredProxyPool',
    'AdvancedProxyPool',
)


class AbstractProxyPool(asyncio.PriorityQueue, LoggerMixin):

    def __init__(self, loop, start_event=None):
        super(AbstractProxyPool, self).__init__(-1)

        self.loop = loop
        self.start_event = start_event
        self.timeout = config['pool']['timeout']

        # Tuple Comparison Breaks in Python3 -  The entry count serves as a
        # tie-breaker so that two tasks with the same priority are returned in
        # the order they were added.
        self.proxy_counter = itertools.count()

        self.last_logged_qsize = None

    @property
    def num_proxies(self):
        return self.qsize()

    async def log_pool_size(self):
        """
        Log Running Low on Proxies Periodically if Change Noticed
        """
        log = self.create_logger('get')

        if self.num_proxies <= 20:
            if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                await log.warning(f'Running Low on Proxies: {self.num_proxies}')

                self.last_logged_qsize = self.num_proxies

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
        try:
            return await asyncio.wait_for(self._get_proxy(), timeout=self.timeout)
        except asyncio.TimeoutError:
            raise PoolNoProxyError()

    async def _get_proxy(self):
        """
        Proxies are always evaluated before being put in queue so we do
        not have to reevaluate.
        """
        ret = await super(AbstractProxyPool, self).get()
        proxy = ret[1]
        return proxy

    async def put(self, proxy):
        count = next(self.proxy_counter)
        priority = proxy.priority(count)
        await super(AbstractProxyPool, self).put((priority, proxy))


class SimpleProxyPool(AbstractProxyPool):

    __name__ = 'Simple Proxy Pool'

    async def prepopulate(self):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        log = self.create_logger('prepopulate')
        await log.start('Prepopulating Proxies')

        proxies = await Proxy.all()
        for proxy in proxies:
            # Do we even want to evaluate for training proxies?
            evaluation = proxy.evaluate_for_pool()
            if evaluation.passed:
                await self.put(proxy, evaluate=False)

        if self.num_proxies == 0:
            await log.error('No Proxies to Prepopulate')
            return

        await log.complete(f"Prepopulated {self.num_proxies} Proxies")

    async def on_proxy_request_error(self, proxy, err):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.

        Case: Error -> Hold Error
        ------------------------
        - Do not include error in historical errors
        - Record error as proxy's last recent error
        - Put in General Pool

        Case: Error -> Not Hold Error
        -----------------------------
        - Record error as proxy's last recent error
        - Include error in proxy's historical errors
        - Put in General Pool

        [x] TODO:
        --------
        For the case of the pool (and not the login handler) the callbacks for
        request and response errors of the proxy are exactly the same, so these
        two methods can be consolidated.
        """
        proxy.note_failure()
        proxy.set_recent_error(err)
        if not err.__hold__:
            proxy.add_error(err)

    async def on_proxy_response_error(self, proxy, err):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.

        Case: Error -> Hold Error
        ------------------------
        - Do not include error in historical errors
        - Record error as proxy's last recent error
        - Put in General Pool

        Case: Error -> Not Hold Error
        -----------------------------
        - Record error as proxy's last recent error
        - Include error in proxy's historical errors
        - Put in General Pool

        [x] TODO:
        --------
        For the case of the pool (and not the login handler) the callbacks for
        request and response errors of the proxy are exactly the same, so these
        two methods can be consolidated.
        """
        proxy.note_failure()
        proxy.set_recent_error(err)
        if not err.__hold__:
            proxy.add_error(err)

    async def on_proxy_success(self, proxy):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.
        """
        proxy.note_success()


class BrokeredProxyPool(SimpleProxyPool):

    __name__ = 'Brokered Proxy Pool'

    def __init__(self, loop, broker, start_event=None):
        super(BrokeredProxyPool, self).__init__(loop, start_event=start_event)
        self.broker = broker

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


class AdvancedProxyPool(BrokeredProxyPool):

    def __init__(self, loop, broker, start_event=None):
        super(AdvancedProxyPool, self).__init__(loop, broker, start_event=start_event)

        self.confirmed = ConfirmedQueue()
        self.held = HeldQueue(self.confirmed, self)

    async def prepopulate(self):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        log = self.create_logger('prepopulate')
        await log.start('Prepopulating Proxies')

        proxies = await Proxy.all()
        for proxy in proxies:
            # Should we use the historical confirmed value or just the last request
            # confirmed value?
            if proxy.confirmed:
                await self.confirmed.put(proxy)
            # If time between attacks isn't sufficiently large, there might be proxies
            # that should still be held.
            elif proxy.hold():
                await self.held.put(proxy)
            else:
                evaluation = proxy.evaluate_for_pool()
                if evaluation.passed:
                    await self.put(proxy, evaluate=False)

        if self.num_proxies == 0:
            await log.error('No Proxies to Prepopulate')
            return

        await log.complete(f"Prepopulated {self.num_proxies} Proxies")
        await log.complete(f"Prepopulated {self.confirmed.qsize()} Good Proxies")

    @property
    def num_proxies(self):
        return (super(BrokeredProxyPool, self).num_proxies +
            self.held.qsize() + self.confirmed.qsize())

    async def on_proxy_request_error(self, proxy, err):
        """
        Callback for case when request notices a request error.

        Always remove from Good Queue if present.

        Case: Error -> Hold Error
        ------------------------
        - Do not include error in historical errors
        - Record error as proxy's last recent error
        - If the proxy's last error is consistent with the new Hold Error, increment
          the timeout.
        - Put in Hold Queue

        Case: Error -> Not Hold Error
        -----------------------------
        - Remove from Hold Queue
        - Record error as proxy's last recent error
        - Include error in proxy's historical errors
        - Put in General Pool

        [x] TODO:
        --------
        For the case of the pool (and not the login handler) the callbacks for
        request and response errors of the proxy are exactly the same, so these
        two methods can be consolidated.
        """
        log = self.create_logger('on_proxy_response_error')
        proxy.note_failure()

        await self.confirmed.remove(proxy)
        proxy.set_recent_error(err)

        if err.__hold__:
            if proxy.last_active_error and proxy.last_active_error.__hold__:
                proxy.increment_timeout(err)
                await log.debug(
                    f'Incremented {err.__subtype__} Timeout to {proxy.timeout(err)}'
                )

            await self.held.put(proxy)
        else:
            proxy.add_error(err)
            # [!] IMPORTANT: This is what is causing confirmed proxies to be in
            # general pool, you can have an error for a confirmed proxy.
            await self.put(proxy)

    async def on_proxy_response_error(self, proxy, err):
        """
        Callback for case when request notices a response error.

        Always remove from Good Queue if present.

        Case: Error -> Hold Error
        ------------------------
        - Do not include error in historical errors
        - Record error as proxy's last recent error
        - If the proxy's last error is consistent with the new Hold Error, increment
          the timeout.
        - Put in Hold Queue

        Case: Error -> Not Hold Error
        -----------------------------
        - Remove from Hold Queue
        - Record error as proxy's last recent error
        - Include error in proxy's historical errors
        - Put in General Pool

        [x] TODO:
        --------
        For the case of the pool (and not the login handler) the callbacks for
        request and response errors of the proxy are exactly the same, so these
        two methods can be consolidated.
        """
        log = self.create_logger('on_proxy_response_error')
        proxy.note_failure()

        await self.confirmed.remove(proxy)
        proxy.set_recent_error(err)

        if err.__hold__:
            if proxy.last_active_error and proxy.last_active_error.__hold__:
                proxy.increment_timeout(err)
                await log.debug(
                    f'Incremented {err.__subtype__} Timeout to {proxy.timeout(err)}'
                )

            await self.held.put(proxy)
        else:
            proxy.add_error(err)
            # [!] IMPORTANT: This is what is causing confirmed proxies to be in
            # general pool, you can have an error for a confirmed proxy.
            await self.put(proxy)

    async def on_proxy_success(self, proxy):
        """
        There is a chance that the proxy is already in the good queue... our
        overridden put method handles that.
        """
        proxy.note_success()
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
        await self.held.recycle()
        await self.log_pool_size()
        return await super(BrokeredProxyPool, self).get()

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
        log = self.create_logger('get')

        proxy = await self.confirmed.get()
        if not proxy:
            proxy = await self.held.get()
            if not proxy:
                proxy = await super(BrokeredProxyPool, self)._get_proxy()

                """
                There can be held proxies in general queue if they were not
                supposed to be held at the time they were initially checked.

                We can fix this problem by checking if the last_error is an error
                that indicates they MIGHT be a holdable proxy, but that might be
                overkill.
                """
                if proxy.hold():
                    await log.warning('Found Hold Proxy in General Pool...', extra={
                        'other': 'Putting Back in Hold Queue and Returning'
                    })
                    await self.held.put(proxy)

                """
                There can be confirmed proxies in general queue if the confirmed
                proxy's last reauest failed.

                We should start checking the last_request_confirmed value instead.
                """
                if proxy.confirmed:
                    await log.error('There should not be confirmed proxies in general pool...',
                        extra={
                            'other': 'Putting Back in Confirmed Queue & Returning'
                        })
                    await self.confirmed.put(proxy)

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
        log = self.create_logger('put')

        if evaluate:
            evaluation = proxy.evaluate_for_pool()
            if not evaluation.passed:
                await log.warning('Cannot Add Proxy to Pool')
                return

        await super(BrokeredProxyPool, self).put(proxy)
