import asyncio
from proxybroker import Broker

from instattack import logger
from instattack.conf import settings
from instattack.lib import starting, stopping
from instattack.src.base import HandlerMixin

from .models import Proxy


log = logger.get_async('Proxy Broker')


class InstattackProxyBroker(Broker, HandlerMixin):

    __name__ = 'Proxy Broker'

    def __init__(self, config, limit=None, **kwargs):
        self.engage(**kwargs)
        self.personal_start_event = asyncio.Event()

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

    @starting
    async def start(self, loop):
        self._started = True

        log.start('Starting Broker')
        await self.find(
            limit=self.limit,
            post=True,
            countries=settings.PROXY_COUNTRIES,
            types=settings.PROXY_TYPES,
        )
        log.complete('Broker Started')
        self.personal_start_event.set()

    async def collect(self):
        if not self._started:
            raise RuntimeError('Cannot collect proxies without starting broker.')

        log.debug('Waiting on Start Event')
        await self.personal_start_event
        log.start('Starting Proxy Collection')

        while True:
            proxy = await self._proxies.get()
            if proxy:
                # Do not save instances now, we save at the end.
                proxy = await Proxy.from_proxybroker(proxy)
                yield proxy
            else:
                log.warning('Null Proxy Returned from Broker... Stopping')
                yield None

    @stopping
    def stop(self, loop, *args, **kwargs):
        """
        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.
        """
        if self._stopped:
            raise RuntimeError('Proxy Broker Already Stopped')

        self._stopped = True
        super(InstattackProxyBroker, self).stop(*args, **kwargs)
        self._proxies.put_nowait(None)
