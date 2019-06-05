from instattack.lib import logger
from instattack.app.exceptions import ProxyPoolError

from .base import ProxySubQueue


class HeldQueue(ProxySubQueue):

    log = logger.get(__name__, 'Held Queue')
    __queueid__ = 'hold'
    __name__ = 'Hold Queue'

    def __init__(self, pool):
        super(HeldQueue, self).__init__(pool)
        self.confirmed = None

    def validate_for_queue(self, proxy):
        """
        Validates whether or not the proxy is allowed to be in the queue.

        For the Hold Queue, we do not have to do this on get(), since we are
        removing the proxy in the put() method, vs. the Confirmed Queue, where
        the proxy stays in the Queue, so has to be validated on get() as well.
        """
        if proxy.confirmed_over_threshold_in_horizon():
            raise ProxyPoolError("Hold Queue: Found Confirmed Proxy")

        # Most Recent Request Confirmed -> Always Should be in Confirmed Queue
        last_request = proxy.last_request(active=True)
        if last_request.confirmed:
            raise ProxyPoolError("Hold Queue: Found Confirmed Proxy")

        if not last_request.was_timeout_error:
            raise ProxyPoolError("Hold Queue: Found Non Holdable Proxy")

    async def get(self):
        """
        Retrieves the first oldest proxy from the queue that should not be held
        anymore.
        """
        async with self.lock:
            for proxy in self._queue:
                self.validate_for_queue(proxy)

                last_request = proxy.last_request(active=True)
                if not proxy.time_since_used > proxy.timeout(last_request.error):
                    self._queue.remove(proxy)
                    return proxy

        if len(self._queue) == 0:
            self.log.info('Hold Queue: No Proxy Ready for Use')
        return None

    # async def recycle(self):
    #     """
    #     Removes proxies from the hold that are no longer required to be in
    #     hold.  If the proxy has been confirmed to have a successful request, the
    #     proxy is put in good, otherwise, the proxy is put back in the pool.

    #     [x] TODO:
    #     --------
    #     Do we want to use active or historical num_requests to determine
    #     if the proxy should be put in the good queue or not?

    #     ^^ Probably not the most important matter, because the errors that cause
    #     a proxy to be put in hold usually mean that there was a success somewhere.
    #     """
    #     async with self.lock:
    #         for proxy in self._queue:
    #             if proxy.hold():
    #                 continue
    #             # Should we use the historical confirmed value or just the last request
    #             # confirmed value?
    #             if proxy.confirmed:
    #                 await self.confirmed.put(proxy)
    #             else:
    #                 await self.pool.put(proxy, evaluate=False)

    async def put(self, proxy):
        """
        [x] Note:
        ---------
        Proxies in Hold Queue are not used by multiple threads simultaneously,
        so when one thread determines that the proxy should be put in the
        Hold Queue, it should not already be in there.
        """
        async with self.lock:
            if proxy in self._queue:
                raise ProxyPoolError('Cannot Add Proxy to Hold Queue')
            proxy.queue_id = 'hold'
            await super(HeldQueue, self).put(proxy)

    async def safe_put(self, proxy):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        async with self.lock:
            if not self.contains(proxy):
                self.put(proxy)

    async def remove(self, proxy):
        async with self.lock:
            if proxy not in self._queue:
                raise ProxyPoolError('Cannot Remove Proxy from Hold Queue')
            self._queue.remove(proxy)

    async def safe_remove(self, proxy):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        async with self.lock:
            if self.contains(proxy):
                self.remove(proxy)
