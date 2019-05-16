from proxybroker import Broker

from instattack import settings
from instattack.lib import starting, stopping
from instattack.mixins import MethodHandlerMixin


class InstattackProxyBroker(Broker, MethodHandlerMixin):

    __name__ = 'Proxy Broker'

    def __init__(self, config, proxies, **kwargs):
        self.engage(**kwargs)

        method_config = config.for_method(self.__method__)
        self.limit = method_config['proxies']['limit']

        super(InstattackProxyBroker, self).__init__(
            proxies,
            max_tries=method_config['proxies']['broker']['max_tries'],
            max_conn=method_config['proxies']['broker']['max_conn'],
            timeout=method_config['proxies']['broker']['timeout'],
            verify_ssl=False,
        )

    @starting
    async def start(self, loop):
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

        self._stopped = True
        super(InstattackProxyBroker, self).stop(*args, **kwargs)
        self._proxies.put_nowait(None)
