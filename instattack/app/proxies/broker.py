import asyncio
import contextlib
from proxybroker import Broker

from instattack.config import settings
from instattack.app.mixins import LoggerMixin

from .models import Proxy


class ProxyBroker(Broker, LoggerMixin):

    __name__ = 'Proxy Broker'

    def __init__(self, loop, limit=None):

        self.loop = loop
        self.config = self.loop.config

        self._stopped = False
        self._started = False

        # ProxyBroker needs a numeric limit unfortunately... if we do not set it,
        # it will be arbitrarily high.
        # TODO: Tie this in with the limit for the pool in some way.
        self.limit = int(limit or self.config['instattack']['proxies']['broker'].get(
            'limit', 10000))
        self._proxies = asyncio.Queue()

        super(ProxyBroker, self).__init__(
            self._proxies,
            max_tries=self.config['instattack']['proxies']['broker']['max_tries'],
            max_conn=self.config['instattack']['proxies']['broker']['max_conn'],
            timeout=self.config['instattack']['proxies']['broker']['timeout'],
            verify_ssl=False,
        )

    @contextlib.asynccontextmanager
    async def session(self):
        log = self.create_logger('session')

        await log.debug('Opening Broker Session')
        try:
            await self.start()
            yield self
        finally:
            await log.debug('Closing Broker Session')
            await self.shutdown()

    async def start(self):
        log = self.create_logger('start')
        await log.start(f'Starting Broker with Limit = {self.limit}')

        self._started = True

        await self.find(
            limit=self.limit,
            post=True,
            countries=settings.PROXY_COUNTRIES,
            types=settings.PROXY_TYPES,
        )

    async def collect(self, save=False):
        log = self.create_logger('collect')

        if self._started:
            raise RuntimeError('Broker should not be started before collect method.')

        async with self.session():
            while True:
                proxy = await self._proxies.get()
                if proxy:
                    # [x] TODO:
                    # Eventually maybe spawn off save into scheduler, although
                    # scheduler is acting weirdly now and swallowing exceptions.
                    proxy, created = await Proxy.update_or_create_from_proxybroker(
                        proxy,
                        save=save
                    )
                    yield proxy, created
                else:
                    await log.debug('Null Proxy Returned from Broker... Stopping')
                    break

    async def shutdown(self):
        """
        Cannot override stop() method, because stop() method must remain synchronous
        since ProxyBroker package attaches signal handlers to it.
        """
        log = self.create_logger('shutdown')

        await log.stop('Shutting Down Proxy Broker')

        self._proxies.put_nowait(None)

        # I think this is throwing an error because ProxyBroker is also stopping
        # it on their own terms.
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
        """
        log = self.create_logger('stop', sync=True)
        if self._stopped:
            raise RuntimeError('Proxy Broker Already Stopped')

        log.start(f'Stopping {self.__name__}')

        # We tried doing this in this manner so that all of the connections/tasks
        # will be closed for the broker when stop() is completed, so they are
        # not seen in the tasks cancelled at the end of the base loop.  It is not
        # working perfectly - some tasks are still remaining unclosed.
        # asyncio.create_task(self._override_done())
        self._done()

        # This might be the cause of the leftover unfinished tasks.
        if self._server:
            self._server.stop()
            self._server = None

        log.complete(f'Stopped {self.__name__}')
