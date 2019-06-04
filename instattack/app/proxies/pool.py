import asyncio
import itertools

from instattack.lib import logger
from instattack.config import config, settings

from instattack.app.exceptions import PoolNoProxyError, ProxyPoolError, ProxyMaxTimeoutError
from instattack.app.models import Proxy

from .queues import ConfirmedQueue, HeldQueue


__all__ = (
    'SimpleProxyPool',
    'BrokeredProxyPool',
    'AdvancedProxyPool',
)


log = logger.get(__name__, subname='Proxy Pool')


class AbstractProxyPool(asyncio.PriorityQueue):

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
        self.original_num_proxies = 0

    @property
    def num_proxies(self):
        return self.qsize()

    async def log_pool_size(self):
        """
        Log Running Low on Proxies Periodically if Change Noticed
        """
        if self.num_proxies <= 20:
            if not self.last_logged_qsize or self.last_logged_qsize != self.num_proxies:
                log.warning(f'Running Low on Proxies: {self.num_proxies}')
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
        proxy.queue_id = 'pool'

        await super(AbstractProxyPool, self).put((priority, proxy))
        return proxy


class SimpleProxyPool(AbstractProxyPool):

    __name__ = 'Simple Proxy Pool'

    async def prepopulate(self, limit=None, confirmed=False):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        log.debug('Prepopulating Proxies')

        self.original_num_proxies = 0

        if confirmed:
            proxies = await Proxy.filter(confirmed=True).all()
        else:
            proxies = await Proxy.all()

        for proxy in proxies:
            await self.put(proxy)

            if limit and self.original_num_proxies == limit:
                break
            self.original_num_proxies += 1

        if self.original_num_proxies == 0:
            log.error('No Proxies to Prepopulate')
            return

        # Non-Broker Proxy Pool: Set start event after prepopulation.
        log.debug(f"Prepopulated {self.original_num_proxies} Proxies")
        self.start_event.set()

    async def on_proxy_error(self, proxy, err):
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
        proxy.add_error(err)

    async def on_proxy_success(self, proxy):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.
        """
        proxy.add_success()


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
        log.debug('Collecting Proxies')

        count = 0
        collect_limit = 10000  # Arbitrarily high for now.

        async for proxy, created in self.broker.collect(save=True):
            evaluation = proxy.evaluate_for_pool()
            if evaluation.passed:
                await self.put(proxy)

                # Set Start Event on First Proxy Retrieved from Broker
                if self.start_event and not self.start_event.is_set():
                    self.start_event.set()
                    log.debug('Setting Start Event', extra={
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

    async def prepopulate(self, limit=None, confirmed=False):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        log.debug('Prepopulating Proxies')

        self.original_num_proxies = 0

        if confirmed:
            proxies = await Proxy.filter(confirmed=True).all()
        else:
            proxies = await Proxy.all()

        for proxy in proxies:
            if limit and self.original_num_proxies == limit:
                break
            proxy = await self.put(proxy)
            if proxy:
                self.original_num_proxies += 1

        if self.original_num_proxies == 0:
            log.error('No Proxies to Prepopulate')
            return

        log.debug(f"Prepopulated {self.original_num_proxies} Proxies")
        log.debug(f"Prepopulated {self.confirmed.qsize()} Good Proxies")

    @property
    def num_proxies(self):
        return (super(AdvancedProxyPool, self).num_proxies +
            self.held.qsize() + self.confirmed.qsize())

    async def on_proxy_error(self, proxy, err):
        """
        Callback for case when request notices a response error.

        [x] TODO:
        --------
        We can probably move the logic below for incrementing the timeout into
        the put method, since proxy.last_request will be the error to this
        method in the .put() method.
        """
        await super(AdvancedProxyPool, self).on_proxy_error(proxy, err)

        last_request = proxy.last_request(active=True)
        if not last_request or not last_request.was_timeout_error:
            proxy.reset_timeouts()

        elif last_request and last_request.was_timeout_error:
            # Leave in Hold Queue and Increment Timeout
            await self.held.raise_if_missing(proxy)
            try:
                proxy.increment_timeout(last_request.error)
            except ProxyMaxTimeoutError as e:
                log.debug(e)

                proxy.reset_timeout(err)
                await self.held.remove(proxy)

                # Don't want to use normal put method because resetting thte timeout
                # will cause the proxy to be put right back into the hold queue.
                return await self.put_in_pool(proxy)

        await self.put(proxy)

    async def on_proxy_success(self, proxy):
        """
        There is a chance that the proxy is already in the good queue... our
        overridden put method handles that.
        """
        await super(AdvancedProxyPool, self).on_proxy_success(proxy)
        if not await self.confirmed.contains(proxy):
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
        # await self.held.recycle()
        await self.log_pool_size()
        return await super(BrokeredProxyPool, self).get()

    async def _get_proxy(self):
        """
        [x] TODO:
        --------
        Update this docstring to reflect current setup.

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
        proxy = await self.confirmed.get()
        if not proxy:
            proxy = await self.held.get()
            if not proxy:
                proxy = await super(BrokeredProxyPool, self)._get_proxy()

                if proxy.confirmed or proxy.last_error(active=True) in settings.TIMEOUT_ERRORS:
                    raise ProxyPoolError("Confirmed or holdable proxies should not be in pool.")

        return proxy

    async def put_in_pool(self, proxy):
        if not proxy.num_requests(active=False, success=True):
            evaluation = proxy.evaluate_for_pool()
            if not evaluation.passed:
                log.debug('Cannot Add Proxy to Pool', extra={
                    'other': str(evaluation)
                })
                return

        await super(BrokeredProxyPool, self).put(proxy)
        return proxy

    async def put(self, proxy, evaluate=True):
        """
        Determines whether or not proxy should be put in the Confirmed Queue,
        the Hold Queue or back in the general pool.  If the proxy is not supposed
        to be held or confirmed, evaluates whether or not the proxy meets the
        specified standards before putting in the general pool.

        [x] NOTE:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the ConfirmedQueue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.

        [x] NOTE:
        ---------
        Do not evaluate for confirmed proxies, it will throw an error because
        we intentionally want to avoid that.  For unconfirmed proxies, we have
        to determine if we want them to be evaluated if they should be held.
        """

        # Proxies that have not been used yet will not have a queue_id, these
        # are always proxies immediately from the prepopulation.

        if not proxy.queue_id:
            if proxy.num_requests(active=False, success=True):
                await self.confirmed.raise_if_present(proxy)
                await self.confirmed.put(proxy)
                return proxy
            else:
                return await self.put_in_pool(proxy)

        else:
            # Guaranteed to be Non Null
            last_request = proxy.last_request(active=True)

            if proxy.queue_id == 'confirmed':
                if last_request.confirmed:

                    # Sanity Check for Now
                    # Should already be in Confirmed Queue - however, another thread
                    # might have removed it in some sort of edge case.
                    missing = await self.confirmed.warn_if_missing(proxy)
                    if missing:
                        await self.confirmed.put(proxy)

                    # Sanity Check for Now
                    await self.held.raise_if_present(proxy)
                    return proxy

                elif last_request.was_timeout_error:
                    # Move to the Hold Queue if not enough time has passed since
                    # the timeout error.  Since the error would have just happened,
                    # this is almost guaranteed to be true.
                    if proxy.time_since_used < proxy.timeout(last_request.error):

                        await self.confirmed.raise_if_missing(proxy)
                        await self.confirmed.remove(proxy)
                        await self.held.raise_if_present(proxy)
                        await self.held.put(proxy)

                        return proxy

                    # Here, enough time has passed since the timeout error. This
                    # would most likely never get reached.
                    else:
                        if proxy.confirmed:
                            await self.confirmed.raise_if_missing(proxy)
                            return proxy
                        else:
                            return await self.put_in_pool(proxy)

            elif proxy.queue_id == 'hold':
                if last_request.confirmed:

                    await self.held.raise_if_missing(proxy)
                    await self.held.remove(proxy)

                    # Always reset timeout when moving out of hold queue.
                    proxy.reset_timeouts()

                    await self.confirmed.raise_if_present(proxy)
                    await self.confirmed.put(proxy)
                    return proxy

                elif last_request.was_timeout_error:

                    # Prevent proxies from staying in hold queue forever by checking
                    # if timeout exceeds the max.
                    if proxy.timeout_exceeds_max(last_request.error):
                        raise RuntimeError('This should not happen, since we should always catch'
                            ' the exception when incremenging timeouts.')
                        # log.debug('Timeout for Proxy in Hold Queue Exceeded Max')

                        # # Always reset timeout when moving out of hold queue.
                        # proxy.reset_timeout(last_request.error)

                        # await self.held.raise_if_missing(proxy)
                        # await self.held.remove(proxy)

                        # # We might want to discard instead of putting back in pool here?
                        # # Could wind up causing a lot of additional unnecessary reqeusts.
                        # return put_in_pool(proxy)

                    else:
                        # Leave in Hold Queue and Increment Timeout
                        await self.held.raise_if_missing(proxy)
                        try:
                            proxy.increment_timeout(last_request.error)
                        except ProxyMaxTimeoutError as e:
                            log.debug(e)
                            proxy.reset_timeout(last_request.error)
                            await self.held.remove(proxy)
                        else:
                            # We might want to discard instead of putting back in pool here?
                            # Could wind up reusing quickly leading to more timeouts.
                            return await self.put_in_pool(proxy)

                else:
                    await self.held.raise_if_missing(proxy)
                    await self.held.remove(proxy)

                    # Always reset timeout when moving out of hold queue.
                    proxy.reset_timeouts()

                    # We might want to discard instead of putting back in pool here?
                    # Could wind up causing a lot of additional unnecessary reqeusts.
                    return await self.put_in_pool(proxy)

            else:
                if last_request.confirmed:
                    await self.confirmed.raise_if_present(proxy)
                    await self.confirmed.put(proxy)
                    return proxy

                # There may be an edge case where the last request error is a timeout
                # error but enough time has passed where it is immediately usable
                # again - but that will just mean it is used from the hold queue
                # faster than usual.
                elif last_request.was_timeout_error:
                    await self.held.raise_if_present(proxy)
                    await self.held.put(proxy)
                    return proxy

                else:
                    # Here, we basically have a proxy from the pool that had a
                    # bad error.  What we should do is evaluate it and put it
                    # back in pool, if it has a confirmed request it will automatically
                    # go back in pool.

                    # [x] TODO: If proxy was confirmed within active life span,
                    # maybe we should put it back in confirmed pool?  Not sure
                    # if this block would ever get reached, but we can leave. code
                    # for now.
                    if proxy.num_requests(active=True, success=True):
                        log.debug('Putting Pool Proxy in Confirmed Queue')
                        await self.confirmed.raise_if_present(proxy)
                        await self.confirmed.put(proxy)
                        return proxy
                    else:
                        return await self.put_in_pool(proxy)
