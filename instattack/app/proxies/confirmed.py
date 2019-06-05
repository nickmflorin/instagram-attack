from instattack.lib import logger
from instattack.app.exceptions import ProxyPoolError

from .base import ProxySubQueue


class ConfirmedQueue(ProxySubQueue):

    log = logger.get(__name__, 'Confirmed Queue')
    __queueid__ = 'confirmed'
    __name__ = 'Confirmed Queue'

    def __init__(self, pool):
        super(ConfirmedQueue, self).__init__(pool)
        self.rotating_index = 0
        self.held = None

    def validate_for_queue(self, proxy):
        """
        Validates whether or not the proxy is allowed to be in the queue.

        For the Confirmed Queue, we do have to do this on get() and put(),
        since proxies are not completely removed from the queue in the
        get() method.
        """
        if not proxy.confirmed_over_threshold_in_horizon():
            raise ProxyPoolError("Confirmed Queue: Found Unconfirmed Proxy")

        last_request = proxy.last_request(active=True)
        if last_request and last_request.was_timeout_error:
            raise ProxyPoolError("Confirmed Queue: Found Holdable Proxy")

    async def get(self):
        """
        Retrieves a proxy from the queue but does not remove it from
        the queue.  This allows multiple threads access to the same proxy.

        Chosen proxy is based on a rotating index that increments on each get()
        call, but resets if it exceeds the limit.  This allows us to not get stuck
        on the first confirmed proxy and allow them to be spread more evenly.
        """
        if self.qsize() != 0:
            proxy = await self._get_proxy()
            self.validate_for_queue(proxy)
            return proxy

            # Last request will be missing for confirmed proxies that are put
            # in the Confirmed Queue during prepopulation.
            # last_request = proxy.last_request(active=True)
            # if not last_request:
            #     return proxy

            # if not last_request.error:
            #     return proxy
            # else:
            #     # This might be expected behavior... Could happen if we are
            #     # not removing from Confirmed Queue unless a certain number of
            #     # errors in a row occur.
            #     if not last_request.was_timeout_error:
            #         raise ProxyPoolError("Confirmed Queue: Proxy's Last Request was Error.")
            #     else:
            #         if proxy.time_since_used > proxy.timeout(last_request.error):
            #             return proxy
            #         else:
            #             self.log.warning(
            #                 'Confirmed Queue: Found Proxy That Should be Held.', extra={
            #                     'other': 'Moving to Hold Queue'
            #                 })

            #             self.held.raise_if_present(proxy)
            #             self.held.put(proxy)

            #             # Recursively call to get another proxy from the active
            #             # queue.
            #             return await self.get()

    async def _get_proxy(self):
        async with self.lock:
            try:
                self.rotating_index += 1
                return self._queue[self.rotating_index]
            except IndexError:
                self.rotating_index = 0
                return self._queue[self.rotating_index]

    async def put(self, proxy):
        """
        [x] Note:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the ConfirmedQueue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.

        This means we have to check before we put in.
        """
        async with self.lock:
            if proxy in self._queue:
                raise ProxyPoolError('Cannot Add Proxy to Confirmed Queue')

            self.validate_for_queue(proxy)
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
        async with self.lock:
            if proxy not in self._queue:
                raise ProxyPoolError('Cannot Remove Proxy from Confirmed Queue')
            self._queue.remove(proxy)

    async def safe_remove(self, proxy):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        async with self.lock:
            if self.contains(proxy):
                self.remove(proxy)
