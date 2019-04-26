from __future__ import absolute_import

import heapq

from proxybroker import Broker, ProxyPool
from proxybroker.errors import NoProxyError

from instattack.conf import settings
from instattack.logger import AppLogger


log = AppLogger(__file__)


__all__ = ('TokenBroker', 'LoginBroker', )


class CustomProxyPool(ProxyPool):
    """
    Imports and gives proxies from queue on demand.

    Overridden because of weird error referenced:

    Weird error from ProxyBroker that makes no sense...
    TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'

    We also want the ability to put None in the queue so that we can stop the
    consumers.
    """

    # TODO: Set these defaults based off of settings or arguments in config.
    def __init__(
        self, proxies, min_req_proxy=5, max_error_rate=0.5, max_resp_time=8
    ):
        self._proxies = proxies
        self._pool = []
        self._min_req_proxy = min_req_proxy

        # We need to use this so that we can tell the difference when the found
        # proxy is None as being intentionally put in the queue to stop the
        # consumer or because there are no more proxies left.
        # I am not 100% sure this will work properly, since the package code
        # might actually put None in when there are no more proxies (see line
        # 112)
        self._stopped = False

        # if num of erros greater or equal 50% - proxy will be remove from pool
        self._max_error_rate = max_error_rate
        self._max_resp_time = max_resp_time

    async def get(self, scheme):
        scheme = scheme.upper()
        for priority, proxy in self._pool:
            if scheme in proxy.schemes:
                chosen = proxy
                self._pool.remove((proxy.priority, proxy))
                break
        else:
            chosen = await self._import(scheme)
        return chosen

    async def _import(self, expected_scheme):
        while True:
            proxy = await self._proxies.get()
            self._proxies.task_done()
            if not proxy:
                # See note above about stopping the consumer and putting None
                # in the proxy.
                if not self._stopped:
                    raise NoProxyError('No more available proxies')
                else:
                    break
            elif expected_scheme not in proxy.schemes:
                await self.put(proxy)
            else:
                return proxy

    async def put(self, proxy):
        """
        TODO:
        -----
        Use information from stat to integrate our own proxy
        models with more information.
        stat: {'requests': 3, 'errors': Counter({'connection_timeout': 1, 'empty_response': 1})}

        We might want to start min_req_per_proxy to a higher level since we
        are controlling how often they are used to avoid max request errors!!!

        We can also prioritize by number of requests to avoid max request errors
        """
        # Overridden Portion
        if proxy is None:
            # ProxyBroker package might actually put None in when there are no
            # more proxies in which case this can cause issues.
            self._stopped = True
            await self._proxies.put(None)

        # Original Portion
        else:
            if proxy.stat['requests'] >= self._min_req_proxy and (
                (proxy.error_rate > self._max_error_rate or
                    proxy.avg_resp_time > self._max_resp_time)
            ):
                log.debug(
                    '%s:%d removed from proxy pool' % (proxy.host, proxy.port)
                )
            else:
                heapq.heappush(self._pool, (proxy.priority, proxy))
            log.debug('%s:%d stat: %s' % (proxy.host, proxy.port, proxy.stat))


class CustomBroker(Broker):
    """
    Overridden to allow custom server to be used and convenience settings
    to be implemented directly from the settings module.

    Also, the proxybroker server stops the main event loop preventing multiple
    brokers from being used.  Even though the .find() method does not use the
    server, that was the original purpose of subclassing the broker and should
    be kept in mind in case we want to reimplement the .serve() functionality.
    requests).
    """

    def __init__(self, *args, **kwargs):
        return super(CustomBroker, self).__init__(
            *args, **self.__broker_settings__,
        )

    def find(self):
        return super(CustomBroker, self).find(**self.__find_settings__)


class TokenBroker(CustomBroker):
    pass
    # __broker_settings__ = settings.BROKER_CONFIG['GET']
    # __find_settings__ = settings.BROKER_CONFIG['FIND']['GET']
    # __serve_settings__ = settings.BROKER_CONFIG['FIND']['GET']


class LoginBroker(CustomBroker):
    pass
    # __broker_settings__ = settings.BROKER_CONFIG['POST']
    # __find_settings__ = settings.BROKER_CONFIG['FIND']['POST']
    # __serve_settings__ = settings.BROKER_CONFIG['SERVE']['POST']
