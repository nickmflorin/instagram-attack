import asyncio

from instattack.lib import logger
from instattack.config import config

from instattack.app.exceptions import ProxyPoolError
from instattack.app.proxies.interfaces import ProxyQueueInterface


__all__ = (
    'ConfirmedQueue',
    'HoldQueue',
)


class ProxyQueue(asyncio.Queue, ProxyQueueInterface):

    def __init__(self, lock):
        super(ProxyQueue, self).__init__(-1)
        self.lock = lock

    async def put(self, proxy):
        proxy.queue_id = self.__queueid__

        if not self.validate_for_queue(proxy):
            if config['instattack']['log.logging']['log_proxy_queue']:
                self.log.debug(f'Cannot Put Proxy in {self.__NAME__}', extra={'proxy': proxy})
            return

        self.raise_for_queue(proxy)
        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(f'Putting Proxy in {self.__NAME__}', extra={'proxy': proxy})
        await super(ProxyQueue, self).put(proxy)

    async def safe_put(self, proxy):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        async with self.lock:
            if not await self.contains(proxy):
                await self.put(proxy)

    async def contains(self, proxy):
        return proxy in self._queue

    async def safe_remove(self, proxy):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        async with self.lock:
            if await self.contains(proxy):
                await self.remove(proxy)

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
            if not await self.contains(proxy):
                raise ProxyPoolError(f'Cannot Remove Proxy from {self.__NAME__}')
            self._queue.remove(proxy)


class ConfirmedQueue(ProxyQueue):

    __NAME__ = 'Confirmed Queue'
    log = logger.get(__name__, __NAME__)

    __queueid__ = 'confirmed'

    def __init__(self, pool, lock):
        super(ConfirmedQueue, self).__init__(lock)
        self.pool = pool
        self.rotating_index = 0
        self.hold = None

    def validate_for_queue(self, proxy):
        return True

    def raise_for_queue(self, proxy):
        """
        Validates whether or not the proxy is allowed to be in the queue.

        For the Confirmed Queue, we do have to do this on get() and put(),
        since proxies are not completely removed from the queue in the
        get() method.
        """
        if not proxy.confirmed():
            raise ProxyPoolError(f"Found Unconfirmed Proxy in {self.__NAME__}")

        last_request = proxy.last_request(active=True)
        if last_request and last_request.was_timeout_error:
            raise ProxyPoolError(f"Found Holdable Proxy in {self.__NAME__}")

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
            self.raise_for_queue(proxy)
            return proxy

    async def _get_proxy(self):
        async with self.lock:
            try:
                self.rotating_index += 1
                return self._queue[self.rotating_index]
            except IndexError:
                self.rotating_index = 0
                return self._queue[self.rotating_index]

    async def move_to_hold(self, proxy):
        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(
                f'Moving Proxy from {self.__NAME__} to {self.hold.__NAME__}',
                extra={'proxy': proxy}
            )

        last_request = proxy.last_request(active=True)
        assert last_request.was_timeout_error

        await self.remove(proxy)
        await self.hold.put(proxy)

    async def move_to_pool(self, proxy):
        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(
                f'Moving Proxy from {self.__NAME__} to {self.pool.__NAME__}',
                extra={'proxy': proxy}
            )

        # Skips validation of pool for confirmed proxies.
        await self.remove(proxy)
        await self.pool.put(proxy, evaluate=False)

    async def put(self, proxy):
        """
        [x] TODO:
        --------
        Depending on treatment of Confirmed Queue when proxies exist in queue
        already, this might be able to moved to base class.

        [x] Note:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the ConfirmedQueue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.

        This means we have to check before we put in.
        """
        async with self.lock:
            # This might happen a lot because confirmed proxies are not removed
            # from the queue!
            if await self.contains(proxy):
                raise ProxyPoolError(f'Cannot Add Proxy to {self.__NAME__}')
            await super(ConfirmedQueue, self).put(proxy)


class HoldQueue(ProxyQueue):

    __NAME__ = 'Hold Queue'
    log = logger.get(__name__, __NAME__)

    __queueid__ = 'hold'

    def __init__(self, pool, lock):
        super(HoldQueue, self).__init__(lock)
        self.pool = pool
        self.confirmed = None

    def validate_for_queue(self, proxy):
        return True

    def raise_for_queue(self, proxy):
        """
        Validates whether or not the proxy is allowed to be in the queue.

        For the Hold Queue, we do not have to do this on get(), since we are
        removing the proxy in the put() method, vs. the Confirmed Queue, where
        the proxy stays in the Queue, so has to be validated on get() as well.
        """
        # Proxy can be confirmed over horizon even if the most recent error is a
        # a timeout error, so we cannot do this:
        # >>> if proxy.confirmed_over_threshold_in_horizon():
        # >>>   raise ProxyPoolError("Hold Queue: Found Confirmed Proxy")

        # Most Recent Request Confirmed -> Always Should be in Confirmed Queue
        last_request = proxy.last_request(active=True)
        if last_request.confirmed:
            raise ProxyPoolError(f"Found Confirmed Proxy in {self.__NAME__}")

        if not last_request.was_timeout_error:
            raise ProxyPoolError(f"Found Non Holdable Proxy in {self.__NAME__}")

    async def get(self):
        async with self.lock:
            for proxy in self._queue:

                # This raise might be overkill?
                self.raise_for_queue(proxy)

                # Do we need to call self.recycle() at some point?  Do we run
                # the risk of proxies getting stuck in here after their timeouts
                # have passed?
                last_request = proxy.last_request(active=True)
                if not proxy.time_since_used > proxy.timeout(last_request.error):
                    await self.remove(proxy)
                    return proxy

        if len(self._queue) == 0:
            self.log.info(f'No Proxy Ready for Use in {self.__NAME__}')
        return None

    async def move_to_confirmed(self, proxy):
        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(
                f'Moving Proxy from {self.__NAME__} to {self.confirmed.__NAME__}',
                extra={'proxy': proxy}
            )
        await self.remove(proxy)
        await self.confirmed.put(proxy)

    async def move_to_pool(self, proxy):
        self.log.debug(
            f'Moving Proxy from {self.__NAME__} to {self.pool.__NAME__}',
            extra={'proxy': proxy}
        )
        await self.remove(proxy)
        await self.pool.put(proxy)

    # async def recycle(self):
    #     """
    #     Removes proxies from the hold that are no longer required to be in
    #     hold.  If the proxy has been confirmed to have a successful request, the
    #     proxy is put in good, otherwise, the proxy is put back in the pool.
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
        [x] TODO:
        --------
        Depending on treatment of Confirmed Queue when proxies exist in queue
        already, this might be able to moved to base class.

        [x] Note:
        ---------
        Proxies in Hold Queue are not used by multiple threads simultaneously,
        so when one thread determines that the proxy should be put in the
        Hold Queue, it should not already be in there.
        """
        async with self.lock:
            if await self.contains(proxy):
                raise ProxyPoolError(f'Cannot Add Proxy to {self.__NAME__}')
            await super(HoldQueue, self).put(proxy)
