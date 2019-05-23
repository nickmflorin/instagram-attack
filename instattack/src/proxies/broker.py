import asyncio
import contextlib
from proxybroker import Broker

from instattack import logger
from instattack import settings
from instattack.src.base import HandlerMixin

from .models import Proxy


log = logger.get_async('Proxy Broker')


class InstattackProxyBroker(Broker, HandlerMixin):

    __name__ = 'Proxy Broker'

    def __init__(self, config, limit=None, **kwargs):
        self.engage(**kwargs)
        self.personal_start_event = asyncio.Event()

        # Don't want to disable entire logger.
        self.log_proxies = config.get('log', False)

        # ProxyBroker needs a numeric limit unfortunately... if we do not set it,
        # it will be arbitrarily high.
        self.limit = limit or config.get('limit', 10000)
        self._proxies = asyncio.Queue()

        # TODO:
        # What would be really cool would be if we could pass in our custom pool
        # directly so that the broker popoulated that queue with the proxies.
        super(InstattackProxyBroker, self).__init__(
            self._proxies,
            max_tries=config['max_tries'],
            max_conn=config['max_conn'],
            timeout=config['timeout'],
            verify_ssl=False,
        )

    @contextlib.asynccontextmanager
    async def session(self, loop):
        log.debug('Starting Proxy Broker Session')
        await self.start(loop)
        try:
            yield self
        finally:
            log.debug('Stopping Proxy Broker Session')
            self.stop(loop)

    async def start(self, loop):
        log = logger.get_async(self.__name__, subname='start')
        log.start('Starting')

        self._started = True

        log.start(f'Starting Broker with Limit = {self.limit}')
        await self.find(
            limit=self.limit,
            post=True,
            countries=settings.PROXY_COUNTRIES,
            types=settings.PROXY_TYPES,
        )
        log.complete('Broker Successfully Started')
        self.personal_start_event.set()

    async def collect(self):
        if not self._started:
            raise RuntimeError('Cannot collect proxies without starting broker.')

        log.debug('Waiting on Start Event')
        await self.personal_start_event.wait()
        log.start('Starting Proxy Collection')

        while True:
            proxy = await self._proxies.get()
            if proxy:
                # Do not save instances now, we are saving in the pool as they
                # are pulled out of the queue.
                proxy = await Proxy.from_proxybroker(proxy)
                if self.log_proxies:
                    log.debug('Broker Returned Proxy', {'proxy': proxy})
                yield proxy
            else:
                log.warning('Null Proxy Returned from Broker... Stopping')
                break

    def stop(self, loop):
        """
        Stop all tasks, and the local proxy server if it's running.

        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.

        We still use the logic in the original Proxy Broker stop method so we do
        not need to call super().
        """
        log = logger.get_async(self.__name__, subname='stop')
        log.stop('Stopping')

        if self._stopped:
            raise RuntimeError('Proxy Broker Already Stopped')

        self._stopped = True
        self._proxies.put_nowait(None)

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
