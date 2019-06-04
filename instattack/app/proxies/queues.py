import asyncio

from instattack.lib import logger
from instattack.app.exceptions import ProxyPoolError


class ProxySubQueue(asyncio.Queue):

    def __init__(self):
        super(ProxySubQueue, self).__init__(-1)
        self.lock = asyncio.Lock()

    async def contains(self, proxy):
        return proxy in self._queue

    async def raise_if_missing(self, proxy):
        if not await self.contains(proxy):
            raise ProxyPoolError(f'Expected Proxy to be in {self.__name__}')

    async def raise_if_present(self, proxy):
        if await self.contains(proxy):
            raise ProxyPoolError(f'Did Not Expect Proxy to be in {self.__name__}')

    async def warn_if_missing(self, proxy):
        try:
            await self.raise_if_missing(proxy)
        except ProxyPoolError as e:
            self.log.warning(e)
            return True
        else:
            return False

    async def warn_if_present(self, proxy):
        try:
            await self.raise_if_present(proxy)
        except ProxyPoolError as e:
            self.log.warning(e)
            return True
        else:
            return False


class ConfirmedQueue(ProxySubQueue):

    log = logger.get(__name__, 'Confirmed Queue')
    __name__ = 'Confirmed Queue'

    def __init__(self):
        super(ConfirmedQueue, self).__init__()
        self.rotating_index = 0

    async def get(self):
        """
        Retrieves a proxy from the queue but does not remove it from
        the queue.  This allows multiple threads access to the same proxy.

        Chosen proxy is based on a rotating index that increments on each get()
        call, but resets if it exceeds the limit.

        [!] Update
        ----------
        We are going to experiment with the simultaneous use of proxies from the
        ConfirmedQueue vs. the regular queue consumer style.
            Might want to add a configuration setting for the above toggle.
        """
        if self.qsize() != 0:
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
            proxy.queue_id = 'confirmed'
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


class HeldQueue(ProxySubQueue):

    log = logger.get(__name__, 'Held Queue')
    __name__ = 'Held Queue'

    def __init__(self, confirmed, pool):
        super(HeldQueue, self).__init__()
        self.confirmed = confirmed
        self.pool = pool

    async def get(self):
        """
        Retrieves the first oldest proxy from the queue that should not be held
        anymore.
        """
        async with self.lock:
            for proxy in self._queue:
                last_request = proxy.last_request(active=True)
                if not proxy.time_since_used > proxy.timeout(last_request.error):
                    self._queue.remove(proxy)
                    return proxy
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
