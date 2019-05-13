from proxybroker import Broker

from instattack import settings
from instattack.lib import starting, stopping
from instattack.core.handlers.base import MethodHandlerMixin


class CustomBroker(Broker, MethodHandlerMixin):

    __name__ = 'Proxy Broker'

    def __init__(self, proxies, config=None, **kwargs):
        self.limit = config['limit']
        self.engage(**kwargs)

        super(CustomBroker, self).__init__(
            proxies,
            max_tries=config['max_tries'],
            max_conn=config['max_conn'],
            timeout=config['timeout'],
            verify_ssl=False,
        )

    @starting
    async def start(self, loop):
        await self.start_event.wait()
        await self.find(
            limit=self.limit,
            post=settings.PROXY_POST[self.__method__],
            countries=settings.PROXY_COUNTRIES[self.__method__],
            types=settings.PROXY_TYPES[self.__method__],
        )

    @stopping
    def stop(self, loop, *args, **kwargs):
        """
        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.
        """
        if self._stopped:
            raise RuntimeError('Proxy Broker Already Stopped')

        self._proxies.put_nowait(None)
        super(CustomBroker, self).stop(*args, **kwargs)
