import asyncio

from instattack.lib import logger
from instattack.config import config

from instattack.app.exceptions import ProxyPoolError, ProxyMaxTimeoutError
from instattack.app.models.proxies import ProxyRequest, Proxy

from .broker import ProxyBroker
from .queues import HoldQueue, ConfirmedQueue
from .interfaces import ProxyManagerInterface


class SimpleProxyManager(ProxyManagerInterface):

    __NAME__ = "Simple Proxy Manager"
    log = logger.get(__name__, __NAME__)

    def __init__(self, loop, pool_cls):

        self.loop = loop
        self.pool = pool_cls(loop)
        self.original_num_proxies = 0

    async def start(self, limit=None, confirmed=False):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.

        [x] TODO:
        ---------
        We are eventually going to need the relationship between prepopulation
        and collection to be more dynamic and adjust, and collection to trigger
        if we are running low on proxies.
        """
        self.log.debug('Prepopulating Proxies')

        filter = {}
        if confirmed:
            filter = {'confirmed': True}

        for proxy in await Proxy.filter(**filter).all():
            if limit and self.num_proxies == limit:
                break

            await self.put(proxy)
            self.original_num_proxies += 1

        if self.num_proxies == 0:
            self.log.error('No Proxies to Prepopulate')
            return

        self.log.info(f"Prepopulated {self.num_proxies} Proxies")

    async def stop(self):
        pass

    async def get(self):
        return await self.pool.get()

    async def put(self, proxy, **kwargs):
        await self.pool.put(proxy, **kwargs)

    async def on_proxy_error(self, proxy, exc):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.
        """
        if config['instattack']['log.logging']['log_request_errors']:
            self.log.error(exc, extra={'proxy': proxy})

        req = ProxyRequest(
            error=exc.__subtype__,
            status_code=exc.status_code,
        )
        proxy.add_failed_request(req)

    async def on_proxy_success(self, proxy):
        """
        For training proxies, we only care about storing the state variables
        on the proxy model, and we do not need to put the proxy back in the
        pool, or a designated pool.
        """
        req = ProxyRequest()
        proxy.add_successful_request(req)


class BrokeredProxyManager(SimpleProxyManager):

    __NAME__ = "Brokered Proxy Manager"
    log = logger.get(__name__, __NAME__)

    def __init__(self, *args, start_event):
        super(BrokeredProxyManager, self).__init__(*args)
        self.broker = ProxyBroker(self.loop)
        self.start_event = start_event

    async def stop(self):
        if self.broker._started:
            self.broker.stop()

    async def collect(self):
        """
        Retrieves proxies from the broker and converts them to our Proxy model.
        The proxy is then evaluated as to whether or not it meets the standards
        specified and conditionally added to the pool.

        [x] TODO:
        ---------
        We need to move this to the appropriate place, most likely in the manager
        class.

        [!] IMPORTANT:
        -------------
        We should maybe make this more dynamic, and add proxies from the broker
        when the pool drops below the limit.

        Figure out how to make the collect limit more dynamic, or at least calculated
        based on the prepopulated limit.
        >>> collect_limit = max(self._maxsize - self.qsize(), 0)
        """
        self.log.debug('Collecting Proxies')

        count = 0
        collect_limit = 10000  # Arbitrarily high for now.

        async for proxy, created in self.broker.collect(save=True):
            evaluation = proxy.evaluate_for_pool()
            if evaluation.passed:
                await self.put(proxy)

                # Set Start Event on First Proxy Retrieved from Broker
                if self.start_event and not self.start_event.is_set():
                    self.start_event.set()
                    self.log.debug('Setting Start Event', extra={
                        'other': 'Broker Started Sending Proxies'
                    })

            if collect_limit and count == collect_limit:
                break
            count += 1

    async def start(self, limit=None, confirmed=False):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.

        [x] TODO:
        ---------
        We are eventually going to need the relationship between prepopulation
        and collection to be more dynamic and adjust, and collection to trigger
        if we are running low on proxies.
        """
        await super(BrokeredProxyManager, self).start(limit=limit, confirmed=confirmed)

        if config['proxies']['pool']['collect']:
            # Pool will set start event when it starts collecting proxies.
            await self.pool.collect()
        else:
            if self.start_event.is_set():
                raise ProxyPoolError('Start Event Already Set')

            self.start_event.set()
            self.log.debug('Setting Start Event', extra={
                'other': 'Proxy Pool Prepopulated'
            })


class SmartProxyManager(BrokeredProxyManager):

    __NAME__ = "Smart Proxy Manager"
    log = logger.get(__name__, __NAME__)

    def __init__(self, loop, pool_cls, start_event=None):
        super(SmartProxyManager, self).__init__(loop, pool_cls, start_event=start_event)
        self.lock = asyncio.Lock()

        self.confirmed = ConfirmedQueue(self.pool, self.lock)
        self.hold = HoldQueue(self.pool, self.lock)

        self.confirmed.hold = self.hold
        self.hold.confirmed = self.confirmed

    async def start(self, **kwargs):
        await super(SmartProxyManager, self).start(**kwargs)
        self.log.info(f"Prepopulated {self.confirmed.num_proxies} Confirmed Proxies")

    @property
    def num_proxies(self):
        return (super(SmartProxyManager, self).num_proxies +
            self.confirmed.num_proxies + self.hold.num_proxies)

    async def on_proxy_error(self, proxy, err):
        """
        Callback for case when request notices a response error.
        """
        await super(SmartProxyManager, self).on_proxy_error(proxy, err)
        await self.put(proxy)

    async def on_proxy_success(self, proxy):
        """
        There is a chance that the proxy is already in the good queue... our
        overridden put method handles that.
        """
        await super(SmartProxyManager, self).on_proxy_success(proxy)
        await self.put(proxy)

    async def get(self):
        """
        [x] NOTE:
        --------
        Logging for pulling proxies out of queues is done in the individual
        queues themselves.
        """
        proxy = await self.confirmed.get()
        if proxy:
            return proxy

        proxy = await self.hold.get()
        if proxy:
            return proxy

        return await super(SmartProxyManager, self).get()

    async def put(self, proxy):
        """
        Determines whether or not proxy should be put in the Confirmed Queue,
        the Hold Queue or back in the general pool.  If the proxy is not supposed
        to be held or confirmed, evaluates whether or not the proxy meets the
        specified standards before putting in the general pool.

        -  If `last_request` is None, that means the put method is being called
           from prepopoulation and the proxy should either be put in the General
           Pool or the Confirmed Qeuue.

        -  If `last_request` is not None, and the proxy queue_id designates it is
           in Confirmed Queue or Hold Queue, have Sub Queue handle the rest of the
           put method.

        - If `last_request` is not None and the queue_id does not designate the
          Hold Queue or the Confirmed Queue, put in General Pool.

        [x] NOTE:
        --------
        There may be an edge case where the last request error is a timeout
        error but enough time has passed for it to be immediately usable
        again -> this just means that it will be pulled from Hold Queue faster
        than it otherwise would though.
        """
        last_request = proxy.requests(-1, active=True)
        if last_request is None:
            assert proxy.queue_id is None

            if proxy.confirmed():
                await self.confirmed.raise_if_present(proxy)
                await self.confirmed.put(proxy, prepopulation=True)
            else:
                # Maybe Limit Evaluation if Proxy was Ever Confirmed?
                await super(SmartProxyManager, self).put(proxy, prepopulation=True)

        else:
            assert proxy.queue_id is not None
            if proxy.queue_id == 'confirmed':
                await self.put_from_confirmed(proxy)

            elif proxy.queue_id == 'hold':
                await self.put_from_hold(proxy)

            else:
                await self.put_from_pool(proxy)

    async def put_from_confirmed(self, proxy):
        """
        Takes a proxy that was taken from the Confirmed Queue and determines how to
        handle it based on the new request appended to the proxy's history.

        Since we do not remove proxies from the Confirmed Queue until they fail,
        we do not need to call `self.confirmed.put(proxy)` to maintain it, we just
        don't take it out.

        [x] NOTE:
        ---------
        Proxies in the manager only move up, and not down (with the exception of
        a proxy moving from confirmed to held).  Once a proxy leaves the pool, to
        either go into the Hold Queue or the Confirmed Queue, leaving either one
        of those queues is an indication that we don't want to use it again, so
        we do not put it back in the General Pool.

        [x] NOTE:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the Confirmed Queue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.

        There seems to be more problems with the Hold Queue and threading race
        conditions than with the Confirmed Queue.

        [x] TODO:
        --------
        Remove sanity checks `raise_if_` once we are more confident in operation
        of the manager.
        """

        # We are temporarily removing proxies from the Confirmed Queue to test out
        # the timeout issues.
        # await self.confirmed.raise_if_missing(proxy)
        await self.hold.warn_if_present(proxy)

        last_request = proxy.requests(-1, active=True)

        # [x] TODO: Figure out a better way of handling this situation.
        # This check has to be done first: proxy can be confirmed over a horizon
        # but still have a more recent timeout error.
        if last_request.was_timeout_error:

            # Since we are removing from Confirmed right now, we don't have to
            # move it, just to put it in.
            await self.hold.put(proxy)
            # await self.confirmed.move_to_hold(proxy)

        # Proxy Still Confirmed Over Horizon - Dont Move Out Yet
        elif proxy.confirmed():
            if not last_request.confirmed:
                errs = proxy.errors_in_horizon()
                if len(errs) != 0:
                    if config['instattack']['log.logging']['log_proxy_queue']:
                        self.log.debug(f'Maintaining Proxy in {self.__NAME__}', extra={
                            'proxy': proxy,
                            'data': {
                                'Num Errors': len(errs),
                            }
                        })

        else:
            # Proxy No Longer Confirmed -> Discard by Removing
            # Temporarily Removing from Confirmed on Get
            # await self.confirmed.remove(proxy)
            pass

    async def put_from_hold(self, proxy):
        """
        Takes a proxy that was taken from the Hold Queue and determines how to
        handle it based on the new request appended to the proxy's history.

        [x] NOTE:
        ---------
        Since the proxy is already in the Hold Queue, the second to last request
        should be a timeout error, otherwise it would not have been sent to the
        Hold Queue to begin with.

        [x] NOTE:
        ---------
        Proxies in the manager only move up, and not down (with the exception of
        a proxy moving from confirmed to held).
            - If a proxy is in the Hold Queue and times out, but then returns a
              confirmed request, we move back up to the Confirmed Queue.
            - If a proxy is in the Hold Queue and returns an error, or times out,
              we discard, not move back to the General Pool.

        [x] TODO:
        --------
        Remove sanity checks `raise_if_` once we are more confident in operation
        of the manager.
        """
        # await self.hold.raise_if_present(proxy)  # Racee Condition - Another thread might be you to it.
        #
        # Don't know why this is failing.
        # await self.confirmed.raise_if_present(proxy)

        # [x] TODO:
        # This Keeps Failing - Only thing I can think of is a Race Condition?
        # We will log warning for now, hopefully find bug.
        last_last_request = proxy.requests(-2, active=True)
        if not last_last_request.was_timeout_error:
            e = ProxyPoolError(
                f"Second to Last Request Should be Timeout Error, "
                f"Not {last_last_request.error}"
            )
            self.log.warning(e)

        last_request = proxy.requests(-1, active=True)

        # Request Confirmed - Move from Hold to Confirmed ^
        if last_request.confirmed:
            # Why were we moving it?  Proxy was removed from hold, it's not
            # in there anymore...
            await self.confirmed.put(proxy)
            # await self.hold.move_to_confirmed(proxy)

        # Another Timeout Error - Increment Timeout and Check Max
        elif last_request.was_timeout_error:
            if last_request.error == last_last_request.error:
                try:
                    proxy.increment_timeout(last_request.error)

                # Proxy Maxes Out -> Discard
                # Should we maybe limit this to discarding only proxies that don't
                # have any recent confirmations?
                except ProxyMaxTimeoutError as e:
                    self.log.info(e)
                    proxy.reset_timeout(last_request.error)
                    pass
                else:
                    # Typical Race Conditions w Hold Queue
                    await self.hold.safe_put(proxy)
            else:
                # Typical Race Conditions w Hold Queue
                await self.hold.safe_put(proxy)
        else:
            # Proxy No Longer Holdable -> Discard
            pass

    async def put_from_pool(self, proxy):
        """
        Takes a proxy that is currently in the General Pool and determines how to
        handle it based on the new request appended to the proxy's history.

        This involves either:
            (1) Putting proxy in Confirmed Queue if it resulted in a successful
                response.
            (2) Putting proxy in Hold Queue if it resulted in a timeout error.
            (3) Putting back in pool.

        [x] TODO:
        --------
        Since we do not return proxies from the Confirmed Queue or Hold Queue
        back to the General Pool, should we discard proxies that have errors
        after being taken out of General Pool?

        For the above, the evaluation will determine whether or not the proxy
        should stay in the General Pool, but this is a little counter-intuitive,
        since we don't apply that same evaluation logic to determine whether or
        not to keep the proxy after it fails in the Confirmed Queue or Hold Queue.

        [x] TODO: Race Condition
        --------
        This is unusual:
        >>>  await self.hold.warn_if_present(proxy)

        This means that a proxy in the pool is already in the Hold Queue - did
        some other thread already put it in there?  Was it not fully removed from
        the Hold Queue?
        """
        await self.hold.warn_if_present(proxy)
        await self.confirmed.raise_if_present(proxy)

        last_request = proxy.requests(-1, active=True)

        if last_request.confirmed:
            await self.confirmed.put(proxy)
        else:
            # [x] NOTE: There really shouldn't be any confirmed proxies in the
            # general pool unless the immediate last request was confirmed.  Once
            # confirmed proxies leave the general pool, they stay out.
            if proxy.confirmed():
                raise ProxyPoolError(
                    f"Should Not be Confirmed Proxy in {self.pool.__NAME__}")

            if last_request.was_timeout_error:
                # Typical Race Conditions w Hold Queue
                await self.hold.safe_put(proxy)
            else:
                await super(SmartProxyManager, self).put(proxy)
