import asyncio
import collections

from instattack.lib import logger
from instattack.config import config

from instattack.app.exceptions import ProxyPoolError, QueueEmpty
from instattack.app.proxies.interfaces import ProxyQueueInterface


__all__ = (
    'ConfirmedQueue',
    'HoldQueue',
)


class ProxyQueue(asyncio.Queue, ProxyQueueInterface):

    def __init__(self, lock):
        super(ProxyQueue, self).__init__(-1)
        self.lock = lock

    async def put(self, proxy, prepopulation=False):
        proxy.queue_id = self.__queueid__

        if not self.validate_for_queue(proxy):
            if config['instattack']['log.logging']['log_proxy_queue']:
                self.log.debug(f'Cannot Put Proxy in {self.__NAME__}', extra={
                    'proxy': proxy
                })
            return

        self.raise_for_queue(proxy)

        if not prepopulation:
            if config['instattack']['log.logging']['log_proxy_queue']:
                self.log.debug(f'Putting Proxy in {self.__NAME__}', extra={
                    'proxy': proxy
                })

        await super(ProxyQueue, self).put(proxy)

    async def safe_put(self, proxy, log=False):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        try:
            await self.put(proxy)
        except ProxyPoolError as e:
            if log:
                self.log.warning(e)

    async def contains(self, proxy):
        return proxy in self._queue

    async def safe_remove(self, proxy, log=False):
        """
        Used ONLY when we cannot be guaranteed of proxy's presence due to race
        conditions.
        """
        try:
            await self.remove(proxy)
        except ProxyPoolError as e:
            if log:
                self.log.warning(e)

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


# Move to Config
MAX_CONFIRMED_PROXIES = 3


class ConfirmedQueue(ProxyQueue):

    __NAME__ = 'Confirmed Queue'
    log = logger.get(__name__, __NAME__)

    __queueid__ = 'confirmed'

    def __init__(self, pool, lock):
        super(ConfirmedQueue, self).__init__(lock)
        self.pool = pool
        self.rotating_index = 0
        self.hold = None

        self.times_used = collections.Counter()
        self.mapped = {}

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

        # THIS CAN HAPPEN
        # If one thread times out with a proxy, it will set it's value to a timeout
        # value before it is necessarily removed from the confirmed queue.
        # last_request = proxy.last_request(active=True)
        # if last_request and last_request.was_timeout_error:
        #     raise ProxyPoolError(f"Found Holdable Proxy in {self.__NAME__}")

    async def get(self):
        """
        Retrieves a proxy from the queue and removes it from the queue after
        a certain number of threads have retrieved it.

        This allows multiple threads access to the same proxy, but does not get
        stuck maxing out with timeout errors due to a large number of threads
        simultaneously using the same proxy.
        """
        try:
            proxy = await self._get_proxy()
        except QueueEmpty as e:
            self.log.warning(e)
            return None
        else:
            self.raise_for_queue(proxy)

            # Temporarily Removing Proxies from Confirmed Queue:
            # Issue is that if a proxy from the confirmed queue raises a too many
            # requests exception, it is likely being used at the same time for
            # several requests, which causes it to timeout immediately.
            # await self.remove(proxy)

            return proxy

    def _delete_nth(self, n):
        self._queue.rotate(-n)
        self._queue.popleft()
        self._queue.rotate(n)

    def _get_nth(self, n):
        self._queue.rotate(-n)
        proxy = self._queue.popleft()
        self._queue.rotate(n)
        return proxy

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
                raise ProxyPoolError(
                    f'Cannot Remove Proxy from {self.__NAME__}',
                    extra={'proxy': proxy}
                )

            ind = self._queue.index(proxy)
            self._delete_nth(ind)
            del self.times_used[proxy.id]
            del self.mapped[proxy.id]

    async def _get_proxy(self):
        """
        [x] TODO:
        --------
        There may be a smarter way to do this, that involves staggering the
        retrieval of the same proxy with asyncio.sleep() based on the number
        of times it was already pulled out.
        """
        async with self.lock:
            least_common = self.times_used.most_common()
            if not least_common:
                raise QueueEmpty(self)

            proxy_id, count = least_common[:-2:-1][0]
            proxy = self.mapped[proxy_id]

            # As proxies are confirmed and put back in, this might cause issues,
            # since there may wind up being more proxies than the limit of giving
            # out.  We will have to decrement the count when a proxy is put back
            # in.
            if count >= MAX_CONFIRMED_PROXIES:
                raise ProxyPoolError('Count %s exceeds %s.' % (count, MAX_CONFIRMED_PROXIES))

            # As proxies are confirmed and put back in,
            if count == MAX_CONFIRMED_PROXIES - 1:
                await self.remove(proxy)

                if config['instattack']['log.logging']['log_proxy_queue']:
                    self.log.debug(f'Returning & Removing Proxy from {self.__NAME__}', extra={
                        'data': {
                            'Times Used': f"{self.times_used[proxy.id] or 0} (Last Allowed)",
                            f'{self.__NAME__} Size': self.qsize(),
                        },
                        'proxy': proxy,
                    })
            else:
                if config['instattack']['log.logging']['log_proxy_queue']:
                    self.log.debug(f'Returning Proxy from {self.__NAME__}', extra={
                        'data': {
                            'Times Used': self.times_used[proxy.id] or 0,
                            f'{self.__NAME__} Size': self.qsize(),
                        },
                        'proxy': proxy,
                    })

            self.times_used[proxy.id] += 1
            return proxy

    async def move_to_hold(self, proxy):
        last_request = proxy.last_request(active=True)
        assert last_request.was_timeout_error

        await self.remove(proxy)
        await self.hold.put(proxy)

        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(
                f'Moving Proxy from {self.__NAME__} to {self.hold.__NAME__}',
                extra={
                    'data': {
                        'Last Request': last_request.error,
                        f"{self.__NAME__} Size": self.qsize(),
                        f"{self.hold.__NAME__} Size": self.hold.qsize(),
                    },
                    'proxy': proxy,
                }
            )

    async def put(self, proxy, prepopulation=False):
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

            if proxy.id in self.times_used:
                raise ProxyPoolError('Did not expect proxy to be in count.')

            # Have to initialize so that the _get_proxy() method can find it.
            self.times_used[proxy.id] = 0
            self.mapped[proxy.id] = proxy

            await super(ConfirmedQueue, self).put(proxy, prepopulation=prepopulation)


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
                self.log.critical(f'Checking if Hold Proxy OK {proxy.time_since_used} > {proxy.timeout(last_request.error)}?',
                extra={'proxy': proxy}) # noqa
                if proxy.time_since_used > proxy.timeout(last_request.error):
                    # await self.remove(proxy)
                    self.log.critical('Hold Proxy Ok')
                    self._queue.remove(proxy)
                    return proxy

        if len(self._queue) == 0:
            self.log.info(f'No Proxy Ready for Use in {self.__NAME__}')
        return None

    async def move_to_confirmed(self, proxy):
        await self.remove(proxy)
        await self.confirmed.put(proxy)

        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(
                f'Moving Proxy from {self.__NAME__} to {self.confirmed.__NAME__}',
                extra={
                    'data': {
                        f"{self.__NAME__} Size": self.qsize(),
                        f"{self.confirmed.__NAME__} Size": self.confirmed.qsize(),
                    },
                    'proxy': proxy,
                }
            )

    async def move_to_pool(self, proxy):
        await self.remove(proxy)
        await self.pool.put(proxy)

        if config['instattack']['log.logging']['log_proxy_queue']:
            self.log.debug(
                f'Moving Proxy from {self.__NAME__} to {self.pool.__NAME__}',
                extra={
                    'data': {
                        f"{self.__NAME__} Size": self.qsize(),
                        f"{self.pool.__NAME__} Size": self.pool.qsize(),
                    },
                    'proxy': proxy,
                }
            )

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
