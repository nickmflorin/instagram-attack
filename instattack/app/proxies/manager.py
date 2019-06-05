from instattack.lib import logger
from instattack.config import config
from instattack.app.exceptions import ProxyPoolError, ProxyMaxTimeoutError

from .confirmed import ConfirmedQueue
from .held import HeldQueue


class ProxySubQueueManager(object):

    log = logger.get(__name__, 'Sub Queue Manager')

    def __init__(self, pool):
        self.pool = pool
        self.confirmed = ConfirmedQueue(pool)
        self.held = HeldQueue(pool)

        self.confirmed.held = self.held
        self.held.confirmed = self.confirmed

    @property
    def num_proxies(self):
        return self.confirmed.num_proxies + self.held.num_proxies

    async def get(self):
        proxy = await self.confirmed.get()
        if proxy:
            return proxy

        proxy = await self.held.get()
        if proxy:
            return proxy

    async def put(self, proxy, req):
        if proxy.queue_id == 'confirmed':
            return await self.put_from_confirmed(proxy, req)

        elif proxy.queue_id == 'hold':
            return await self.put_from_hold(proxy, req)

        else:
            assert proxy.queue_id == 'pool'
            return await self.put_from_pool(proxy, req)

    async def put_from_confirmed(self, proxy, req):
        """
        [x] NOTE:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the Confirmed Queue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.
        """

        await self.confirmed.raise_if_missing(proxy)  # Sanity Check for Now

        # Race Condition
        await self.held.warn_if_present(proxy)  # Sanity Check for Now

        # Assertion Not Valid because of Confirmation Horizons
        # last_last_request = proxy.requests(-2, active=True)
        # if last_last_request:
        #     assert last_last_request.confirmed

        # Request Confirmed Again - Maintain in Confirmed Queue
        if req.confirmed:
            return proxy

        # Timeout Error in Confirmed - Don't need to increment timeout, but also
        # don't want to worry about confirmation horizon.

        # IMPORTANT!!!!
        # NOTE: THIS MAY CAUSE ERRORS - The proxy might still be confirmed over
        # a given horizon, but there was a timeout error in there.  We need to fix
        # this.
        elif req.was_timeout_error:
            self.log.info('Moving Proxy from Confirmed to Hold Queue')
            await self.confirmed.remove(proxy)
            await self.held.put(proxy)
            return proxy

        else:
            # Keep in Confirmed
            if proxy.confirmed_over_threshold_in_horizon():

                requests = proxy.confirmations_in_horizon(
                    horizon=config['pool']['confirmation_horizon'])
                if any([req.error for req in requests]):
                    self.log.debug('Keeping Proxy in Confirmed Even w/ Error')

                return proxy

            else:
                self.log.info('Moving Proxy from Confirmed to General Pool')
                await self.confirmed.remove(proxy)
                await self.pool.put_in_pool(proxy)
                return proxy

    async def put_from_hold(self, proxy, req):
        await self.held.raise_if_missing(proxy)  # Sanity Check for Now
        await self.confirmed.raise_if_present(proxy)  # Sanity Check for Now

        last_last_request = proxy.requests(-2, active=True)
        assert last_last_request.was_timeout_error

        # Request Confirmed - Move from Hold to Confirmed
        if req.confirmed:
            self.log.info('Moving Proxy from Hold to Confirmed Queue')
            await self.held.remove(proxy)
            await self.confirmed.put(proxy)
            return proxy

        # Another Timeout Error - Increment Timeout and Check Max
        elif req.was_timeout_error and req.error == last_last_request.error:
            try:
                proxy.increment_timeout(req.error)
            except ProxyMaxTimeoutError as e:
                self.log.info(e)
                proxy.reset_timeout(req.error)

                self.log.info('Moving Proxy from Hold to General Pool')
                await self.held.remove(proxy)
                return await self.pool.put_in_pool(proxy)
            else:
                # Race Condition
                await self.held.safe_put(proxy)
                return proxy

        else:
            self.log.info('Moving Proxy from Hold to General Pool')
            # Race Condition
            await self.confirmed.safe_remove(proxy)
            await self.pool.put_in_pool(proxy)
            return proxy

    async def put_from_pool(self, proxy, req):
        # Race Condition
        # TODO: This means some other process put it in the hold queue already?  Or maybe that
        # it just wasn't fully removed from the hold queue yet?  Either way, we should figure
        # it out and possibly readjust here.
        await self.held.warn_if_present(proxy)

        await self.confirmed.raise_if_present(proxy)  # Sanity Check for Now

        # Do we need to check over horizon here?  I don't think so, since it would
        # already be put in the confirmed queue.
        if req.confirmed:
            await self.confirmed.put(proxy)
        elif req.was_timeout_error:
            # Race Condition
            await self.held.safe_put(proxy)
        else:
            raise ProxyPoolError("Invalid proxy submitted to sub queue.")
