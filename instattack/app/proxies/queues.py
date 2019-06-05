import asyncio

from instattack.lib import logger
from instattack.app.exceptions import ProxyPoolError, ProxyMaxTimeoutError


NUM_CONFIRMATION_THRESHOLD = 3


class ProxySubQueueManager(object):

    def __init__(self, pool):
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
        """
        [x] NOTE:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the Confirmed Queue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.
        """
        last_last_request = proxy.requests(-2, active=True)

        if proxy.queue_id == 'confirmed':
            await self.confirmed.raise_if_missing(proxy)  # Sanity Check for Now
            await self.held.raise_if_present(proxy)  # Sanity Check for Now

            # Can be None for Prepopulated Confirmed Proxies
            if last_last_request:
                assert last_last_request.confirmed

            # Request Confirmed Again - Maintain in Confirmed Queue
            if req.confirmed:
                return proxy

            # Timeout Error in Confirmed - Don't need to increment timeout
            elif req.was_timeout_error:
                self.log.debug('Moving Proxy from Confirmed to Hold Queue')
                await self.confirmed.remove(proxy)
                await self.held.put(proxy)
                return proxy

            else:
                requests = proxy.requests(active=True)[int(-1 * NUM_CONFIRMATION_THRESHOLD):]

                # Keep in Confirmed
                if len(requests) < NUM_CONFIRMATION_THRESHOLD:
                    self.log.debug('Keeping Proxy in Confirmed Even w/ Error')
                    return proxy
                elif any([req.confirmed for req in requests]):
                    self.log.debug('Keeping Proxy in Confirmed Even w/ Error')
                    return proxy
                else:
                    self.log.debug('Moving Proxy from Confirmed to General Pool')
                    await self.confirmed.remove(proxy)
                    await self.pool.put_in_pool(proxy)
                    return proxy

        elif proxy.queue_id == 'hold':
            await self.held.raise_if_missing(proxy)  # Sanity Check for Now
            await self.confirmed.raise_if_present(proxy)  # Sanity Check for Now

            assert last_last_request.was_timeout_error

            # Request Confirmed - Move from Hold to Confirmed
            if req.confirmed:
                self.log.debug('Moving Proxy from Hold to Confirmed Queue')
                await self.held.remove(proxy)
                await self.confirmed.put(proxy)
                return proxy

            # Another Timeout Error - Increment Timeout and Check Max
            elif req.was_timeout_error and req.error == last_last_request.error:
                try:
                    proxy.increment_timeout(req.error)
                except ProxyMaxTimeoutError as e:
                    self.log.debug(e)
                    proxy.reset_timeout(req.error)

                    self.log.debug('Moving Proxy from Hold to General Pool')
                    await self.held.remove(proxy)
                    return await self.put_in_pool(proxy)
                else:
                    await self.held.put(proxy)
                    return proxy

            else:
                self.log.debug('Moving Proxy from Hold to General Pool')
                await self.confirmed.remove(proxy)
                await self.pool.put_in_pool(proxy)
                return proxy

        else:
            assert proxy.queue_id == 'pool'
            await self.held.raise_if_present(proxy)  # Sanity Check for Now
            await self.confirmed.raise_if_present(proxy)  # Sanity Check for Now

            if req.confirmed:
                await self.confirmed.put(proxy)
            elif req.was_timeout_error:
                await self.held.put(proxy)
            else:
                raise ProxyPoolError("Invalid proxy submitted to sub queue.")


class ProxySubQueue(asyncio.Queue):

    def __init__(self, pool):
        super(ProxySubQueue, self).__init__(-1)

        self.pool = pool
        self.lock = asyncio.Lock()

    @property
    def num_proxies(self):
        return self.qsize()

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

    def __init__(self, pool):
        super(ConfirmedQueue, self).__init__(pool)
        self.rotating_index = 0
        self.held = None

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
                    proxy = self._queue[self.rotating_index]
                except IndexError:
                    self.rotating_index = 0
                    proxy = self._queue[self.rotating_index]

            # Sanity Check
            last_request = proxy.last_request(active=True)
            if last_request:
                if last_request.error:
                    # This is Expected Behavior!  Historically Confirmed vs. Last Request
                    self.log.debug("Confirmed Queue Proxy's Last Request was Error.")

                if last_request.was_timeout_error:
                    if proxy.time_since_used > proxy.timeout(last_request.error):
                        return proxy
                    else:
                        self.log.debug('Confirmed Queue Proxy Should be Held...')

                        self.held.raise_if_present(proxy)
                        self.held.put(proxy)

                        # Recursion
                        return await self.get()

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

    def __init__(self, pool):
        super(HeldQueue, self).__init__(pool)
        self.confirmed = None

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
