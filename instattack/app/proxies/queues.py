import asyncio

from instattack.app.mixins import LoggerMixin


class ConfirmedQueue(asyncio.Queue, LoggerMixin):

    __name__ = 'Confirmed Queue'

    def __init__(self):
        super(ConfirmedQueue, self).__init__(-1)
        self.lock = asyncio.Lock()

    async def get(self):
        """
        Retrieves the oldest proxy from the queue but does not remove it from
        the queue.  This allows multiple threads access to the same proxy.

        [!] Update
        ----------
        We are going to experiment with the simultaneous use of proxies from the
        ConfirmedQueue vs. the regular queue consumer style.
            Might want to add a configuration setting for the above toggle.
        """
        log = self.create_logger('get')

        if self.qsize() != 0:
            async with self.lock:
                # Not sure if this is true or not - but we should maybe move to
                # the hold queue if this is the case.  It might be being caused
                # by initial population when time between attacks isn't large
                # enough...
                for proxy in self._queue:
                    if proxy.hold():
                        await log.warning('Should not be a held proxy in confirmed queue.')
                    else:
                        return proxy
            # return await super(ConfirmedQueue, self).get()

    async def put(self, proxy):
        """
        [x] Note:
        ---------
        Because proxies in the ConfirmedQueue are used simultaneously by multiple
        threads at the same time, and a proxy from the ConfirmedQueue is likely to
        cause subsequent successful responses, it is likely that the proxy is
        already in the ConfirmedQueue.
        """
        async with self.lock:
            if proxy not in self._queue:
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
            if proxy in self._queue:
                self._queue.remove(proxy)


class HeldQueue(asyncio.Queue, LoggerMixin):

    __name__ = 'Held Queue'

    def __init__(self, confirmed, pool):
        super(HeldQueue, self).__init__(-1)
        self.confirmed = confirmed
        self.pool = pool
        self.lock = asyncio.Lock()

    async def get(self):
        """
        Retrieves the first oldest proxy from the queue that should not be held
        anymore.
        """
        async with self.lock:
            for proxy in self._queue:
                if not proxy.hold():
                    # This prevents the simultaneous thread use.
                    self._queue.remove(proxy)
                    return proxy
        return None

    async def recycle(self):
        """
        Removes proxies from the hold that are no longer required to be in
        hold.  If the proxy has been confirmed to have a successful request, the
        proxy is put in good, otherwise, the proxy is put back in the pool.

        [x] TODO:
        --------
        Do we want to use active or historical num_requests to determine
        if the proxy should be put in the good queue or not?

        ^^ Probably not the most important matter, because the errors that cause
        a proxy to be put in hold usually mean that there was a success somewhere.
        """
        async with self.lock:
            for proxy in self._queue:
                if proxy.hold():
                    continue
                # Should we use the historical confirmed value or just the last request
                # confirmed value?
                if proxy.confirmed:
                    await self.confirmed.put(proxy)
                else:
                    await self.pool.put(proxy, evaluate=False)

    async def put(self, proxy):
        """
        [x] Note:
        ---------
        Proxies in Hold Queue are not used by multiple threads simultaneously,
        so when one thread determines that the proxy should be put in the
        Hold Queue, it should not already be in there.
        """
        log = self.create_logger('add')

        async with self.lock:
            if proxy not in self._queue:
                await super(HeldQueue, self).put(proxy)
            else:
                # This is Not a Race Condition
                await log.warning('Cannot Add Proxy to Hold Queue', extra={
                    'other': 'Proxy Already in Hold Queue',
                    'proxy': proxy,
                })

    async def remove(self, proxy):
        log = self.create_logger('remove')

        async with self.lock:
            if proxy in self._queue:
                self._queue.remove(proxy)
            else:
                # This is Not a Race Condition
                await log.warning('Cannot Remove Proxy from Hold Queue', extra={
                    'other': 'Proxy Not in Hold Queue',
                    'proxy': proxy,
                })
