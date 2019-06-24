import asyncio
import contextlib
from proxybroker import Broker

from instattack import settings

from instattack.lib import logger
from instattack.core.models import Proxy


log = logger.get(__name__, subname='Proxy Broker')


class ProxyBroker(Broker):

    __name__ = 'Proxy Broker'

    def __init__(self, loop, limit=None):
        """
        If we want the broker to run until we manually stop it, we still need
        to set a limit on initialization for the Proxy Broker package, so we
        set that arbitrarily high.

        [x] TODO:
        ---------
        The limit of the broker (i.e. the collect limit) needs to eventually
        be tied in with the pool in some way, and collection needs to be triggered
        when we start runnign low on prepopulated proxies.
        """
        self.loop = loop
        self._stopped = False
        self._started = False

        self.limit = int(limit or settings.proxies.broker.get('limit', 10000))
        self._proxies = asyncio.Queue()

        super(ProxyBroker, self).__init__(
            self._proxies,
            max_tries=settings.proxies.broker.broker_max_tries,
            max_conn=settings.proxies.broker.broker_max_conn,
            timeout=settings.proxies.broker.broker_timeout,
            verify_ssl=False,
        )

    @contextlib.asynccontextmanager
    async def session(self):
        log.debug('Opening Broker Session')
        try:
            await self.start()
            yield self
        finally:
            log.debug('Closing Broker Session')
            await self.shutdown()

    async def start(self):
        """
        [x] TODO:
        --------
        Start storing countries in database and allow configuration to specify
        and restrict the countries of the proxies we use or collect.
        """
        log.debug(f'Starting Broker with Limit = {self.limit}')
        self._started = True

        await self.find(
            limit=self.limit,
            post=True,
            countries=settings.PROXY_COUNTRIES,
            types=settings.PROXY_TYPES,  # HTTP Only
        )

    async def collect(self, save=False):
        """
        [x] TODO:
        --------
        Eventually spawn off Proxy.update_or_create_from_proxybroker() save into
        a scheduler or loop.call_soon() type of task.
        """
        if self._started:
            raise RuntimeError('Broker should not be started before collect method.')

        async with self.session():
            while True:
                proxy = await self._proxies.get()
                if proxy:
                    proxy, created = await Proxy.update_or_create_from_proxybroker(
                        proxy,
                        save=save
                    )
                    yield proxy, created
                else:
                    log.info('Null Proxy Returned from Broker... Stopping')
                    break

    async def shutdown(self):
        """
        Cannot override stop() method, because stop() method must remain synchronous
        since ProxyBroker package attaches signal handlers to it.

        If we are stopping the broker on our own accord, we need to set a flag
        `_stopped`, since Proxy Broker also seems to stop it occasionally on
        their own accord, which can lead to errors.
        """
        log.debug('Shutting Down Proxy Broker')
        self._proxies.put_nowait(None)

        if not self._stopped:
            self.stop()
            self._stopped = True

    def stop(self):
        """
        Stop all tasks, and the local proxy server if it's running.

        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.

        We still use the logic in the original Proxy Broker stop method so we do
        not need to call super().

        [x] NOTE:
        --------
        We tried creating an async version of _done(), so we could asynchronously
        call cancel_remaining_tasks() to cleanup (we cannot override _done() with
        an async method because of reason above):

        >>> asyncio.create_task(self._override_done())v

        It was not working well, there were still some lingering tasks leftover
        by the time the main loop shutdown.
        """
        if self._stopped:
            raise RuntimeError('Proxy Broker Already Stopped')

        log.debug(f'Stopping {self.__name__}')
        self._done()

        # This might be the cause of the leftover unfinished tasks.  This is
        # Proxy Broker code.
        if self._server:
            self._server.stop()
            self._server = None

        log.debug(f'Stopped {self.__name__}')
