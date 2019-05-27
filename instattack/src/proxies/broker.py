import asyncio
import contextlib
from proxybroker import Broker

from instattack import settings
from instattack.src.base import HandlerMixin
from instattack.src.utils import cancel_remaining_tasks

from .models import Proxy


class ProxyBroker(Broker, HandlerMixin):

    __name__ = 'Proxy Broker'
    __logconfig__ = 'proxy_broker'

    def __init__(self, config, limit=None):

        self._stopped = False
        self.config = config

        # ProxyBroker needs a numeric limit unfortunately... if we do not set it,
        # it will be arbitrarily high.
        self.limit = limit or config['proxies']['broker'].get('limit', 10000)
        self._proxies = asyncio.Queue()

        super(ProxyBroker, self).__init__(
            self._proxies,
            max_tries=config['proxies']['broker']['max_tries'],
            max_conn=config['proxies']['broker']['max_conn'],
            timeout=config['proxies']['broker']['timeout'],
            verify_ssl=False,
        )

    @contextlib.asynccontextmanager
    async def session(self, loop):
        log = self.create_logger(subname='session', ignore_config=True)

        await log.start('Opening Broker Session')
        await self.start(loop)
        try:
            yield self
        finally:
            await log.complete('Closing Broker Session')
            await self.shutdown(loop)

    async def start(self, loop):
        log = self.create_logger(subname='start')
        await log.start(f'Starting Broker with Limit = {self.limit}')

        self._started = True

        await self.find(
            limit=self.limit,
            post=True,
            countries=settings.PROXY_COUNTRIES,
            types=settings.PROXY_TYPES,
        )

    async def collect(self, loop, save=False):
        log = self.create_logger(subname='collect')

        if self._started:
            raise RuntimeError('Broker should not be started before collect method.')

        async with self.session(loop):
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
                    if self.log_proxies:
                        await log.debug('Broker Returned Proxy', extra={'proxy': proxy})
                    yield proxy, created
                else:
                    await log.warning('Null Proxy Returned from Broker... Stopping')
                    break

    async def shutdown(self, loop):
        """
        Cannot override stop() method, because stop() method must remain synchronous
        since ProxyBroker package attaches signal handlers to it.
        """
        log = self.create_logger(subname='shutdown')
        await log.stop('Shutting Down Proxy Broker')

        self._proxies.put_nowait(None)

        # I think this is throwing an error because ProxyBroker is also stopping
        # it on their own terms.
        if not self._stopped:
            self.stop(loop)
            self._stopped = True

        # If we do not do this here, these tasks can raise exceptions in our
        # shutdown method.
        await log.debug('Cancelling Proxy Broker Tasks')
        await cancel_remaining_tasks(
            futures=self._all_tasks,
            silence_exceptions=True,
            log_exceptions=False,
        )

    def stop(self, loop):
        """
        Stop all tasks, and the local proxy server if it's running.

        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.

        We still use the logic in the original Proxy Broker stop method so we do
        not need to call super().
        """
        if self._stopped:
            raise RuntimeError('Proxy Broker Already Stopped')

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
