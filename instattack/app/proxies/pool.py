import asyncio
import itertools

from instattack.lib import logger
from instattack.config import config

from instattack.app.exceptions import PoolNoProxyError
from instattack.app.models import Proxy, ProxyRequest

from .queues import ProxySubQueueManager


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

    async def on_proxy_error(self, proxy, exc):
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
        assert not type(exc) is str
        req = ProxyRequest(
            error=exc.__subtype__,
            status_code=exc.status_code,
        )
        proxy.add_failed_request(req)
        return req

    async def on_proxy_success(self, proxy):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.
        """
        req = ProxyRequest()
        proxy.add_successful_request(req)
        return req


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
        self.subqueue = ProxySubQueueManager(self)

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
        log.debug(f"Prepopulated {self.subqueue.confirmed.qsize()} Good Proxies")

    @property
    def num_proxies(self):
        return super(AdvancedProxyPool, self).num_proxies + self.subqueue.num_proxies

    async def on_proxy_error(self, proxy, err):
        """
        Callback for case when request notices a response error.
        """
        req = await super(AdvancedProxyPool, self).on_proxy_error(proxy, err)
        await self.put(proxy, req=req)

    async def on_proxy_success(self, proxy):
        """
        There is a chance that the proxy is already in the good queue... our
        overridden put method handles that.
        """
        req = await super(AdvancedProxyPool, self).on_proxy_success(proxy)
        await self.put(proxy, req=req)

    async def get(self):
        """
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
        proxy = await self.subqueue.get()
        if proxy:
            return proxy

        proxy = await super(BrokeredProxyPool, self)._get_proxy()

        last_request = proxy.requests(-1, active=True)
        if last_request:
            assert not last_request.confirmed

        # Note that the last request can be a timeout error if it maxed out.
        # last_request = proxy.requests(-1, active=True)
        # assert not last_request.was_timeout_error
        # Also, the proxy can be confirmed, if it had enough recent errors.

        return proxy

    async def put(self, proxy, req=None):
        """
        Determines whether or not proxy should be put in the Confirmed Queue,
        the Hold Queue or back in the general pool.  If the proxy is not supposed
        to be held or confirmed, evaluates whether or not the proxy meets the
        specified standards before putting in the general pool.

        If `req` is None, that means the put method is being called from the
        prepopulation, and the proxy has no active history.
        """
        threshold = config['pool']['num_confirmation_threshold']

        if not req:
            assert proxy.queue_id is None

            last_request = proxy.requests(-1, active=True)
            assert last_request is None

            # [x] TODO: Move the threshold for historical confirmations to config.
            if proxy.num_requests(active=False, success=True) >= threshold:  # noqa
                await self.subqueue.confirmed.raise_if_present(proxy)
                await self.subqueue.confirmed.put(proxy)
            else:
                await self.put_in_pool(proxy)

            return proxy

        else:
            # If proxy is in Confirmed Queue or Hold Queue, have Sub Queue handle
            # the rest of the put method.  Sub Queue will put back in the General
            # Pool if necessary.
            assert proxy.queue_id is not None
            if proxy.queue_id in ('confirmed', 'hold'):
                return await self.subqueue.put(proxy, req)

            else:
                """
                [x] NOTE:
                --------
                There may be an edge case where the last request error is a timeout
                error but enough time has passed for it to be immediately usable
                again.

                This just means that it will be pulled from hole queue faster
                than it otherwise would though.
                """
                if req.confirmed or req.was_timeout_error:
                    return await self.subqueue.put(proxy, req)

                # Normal Error, Keep in Pool if Passes Eval
                else:
                    # Previous previous request should not be a timeout error
                    # or confirmed, otherwise proxy would have switched to the
                    # Sub Queue
                    last_last_request = proxy.requests(-2, active=True)
                    if last_last_request:
                        # [x] Not So Sure About These
                        assert not last_last_request.was_timeout_error
                        assert not last_last_request.confirmed
                    return await self.put_in_pool(proxy)

    async def put_in_pool(self, proxy):
        """
        We do not evaluate proxies that have had a prior confirmation by default,
        although we should start setting a stricter threshold for avoiding
        evaluation.

        [x] NOTE:
        ---------
        Do not evaluate for confirmed proxies, that have a number of historical
        confirmations above a threshold.
        """
        threshold = config['pool']['num_confirmation_threshold']

        if not proxy.num_requests(active=False, success=True) < threshold:  # noqa
            evaluation = proxy.evaluate_for_pool()
            if not evaluation.passed:
                log.debug('Cannot Add Proxy to Pool', extra={
                    'other': str(evaluation)
                })
                return

        await super(BrokeredProxyPool, self).put(proxy)
        return proxy
