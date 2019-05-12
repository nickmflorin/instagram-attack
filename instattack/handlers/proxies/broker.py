from proxybroker import Broker

from instattack.handlers.control import Control
from instattack.handlers.utils import starting, stopping


class CustomBroker(Broker, Control):

    __name__ = 'Proxy Broker'

    def __init__(
        self,
        proxies,
        max_tries=None,
        max_conn=None,
        timeout=None,
        verify_ssl=False,
        limit=None,
        post=False,
        countries=None,
        types=None,
        **kwargs,
    ):
        self.broker_args = {
            'max_tries': max_tries,
            'max_conn': max_conn,
            'timeout': timeout,
            'verify_ssl': verify_ssl
        }
        self.find_args = {
            'limit': limit,
            'post': post,
            'countries': countries or [],
            'types': types
        }

        self.engage(**kwargs)
        super(CustomBroker, self).__init__(proxies, **self.broker_args)

    @starting
    async def find(self, loop):
        self.log.debug('Waiting on Start Event...')
        await self.start_event.wait()
        await super(CustomBroker, self).find(**self.find_args)

    @stopping
    def stop(self, loop, *args, **kwargs):
        """
        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.
        """
        self._proxies.put_nowait(None)
        super(CustomBroker, self).stop(*args, **kwargs)

    def increment_limit(self):
        """
        Sometimes the proxy pool might notice something wrong with the proxies
        that are being returned from the broker, and it cannot use one.  In that
        case, if we still want to have the number of proxies defined by limit in
        the pool, we have to increment the limit of the broker.

        There might be other edge case logic we have to incorporate here.
        """
        self._limit += 1
