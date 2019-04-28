from __future__ import absolute_import

import heapq

from proxybroker import ProxyPool

from instattack.logger import AppLogger

from .exceptions import ProxyPoolException, NoProxyError


__all__ = ('CustomProxyPool', )


class CustomProxyPool(ProxyPool):
    """
    Imports and gives proxies from queue on demand.

    Overridden because of weird error referenced:

    Weird error from ProxyBroker that makes no sense...
    TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'

    We also want the ability to put None in the queue so that we can stop the
    consumers.
    """
    __name__ = 'Custom Proxy Pool'
    log = AppLogger(__name__)

    def __init__(
        self,
        proxies,
        min_req_proxy=None,
        max_error_rate=None,
        max_resp_time=None,
    ):
        self._proxies = proxies
        self._pool = []

        # if num of erros greater or equal 50% - proxy will be remove from pool
        self._max_error_rate = max_error_rate
        self._max_resp_time = max_resp_time
        self._min_req_proxy = min_req_proxy

        # We need to use this so that we can tell the difference when the found
        # proxy is None as being intentionally put in the queue to stop the
        # consumer or because there are no more proxies left from the Broker.
        self._stopped = False

    async def get(self, scheme):
        scheme = scheme.upper()

        if self._stopped:
            raise ProxyPoolException("Cannot get proxy from stopped pool.")

        for priority, proxy in self._pool:
            if scheme in proxy.schemes:
                self.log.debug('Found Proxy in Populated _pool', extra={'proxy': proxy})
                self._pool.remove((proxy.priority, proxy))
                return proxy

        else:
            if len(self._pool) != 0:
                self.log.debug('No Valid Schemes for Proxies in _pool')
            chosen = await self._import(scheme)

        return chosen

    async def _import(self, expected_scheme):
        """
        If the proxy that is retrieved from the self._proxies Queue is None,
        but self._stopped is set, that means it was intentionally put in to shut
        down the pool.

        Otherwise, if the proxy is None and self._stopped is not set, than this
        indicates that the ProxyBroker has reached its limit, so we raise the
        NoProxyError.
        """
        while True:
            self.log.debug('Waiting on Proxy from Original Queue')
            proxy = await self._proxies.get()
            # self._proxies.task_done()  # In Original Code

            if not proxy:
                if not self._stopped:
                    raise NoProxyError()
                else:
                    # This block only gets reached after the self.put method is
                    # called with a proxy value of None, which triggers the self.stop()
                    # method.  That means that all we have to do here is exit
                    # the loop.
                    break

            elif expected_scheme not in proxy.schemes:
                self.log.debug('Expected Scheme not in Proxy Schemes', extra={'proxy': proxy})
                await self.put(proxy)
            else:
                self.log.debug('Returning Proxy', extra={'proxy': proxy})
                return proxy

    async def stop(self):
        with self.log.start_and_done(f"Stopping {self.__name__}"):
            self._stopped = True
            self._pool = []
            await self._proxies.put(None)

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
        # Overridden Portion - We might want to put None in the consumed proxies,
        # so taht the block that logs that the pool is stoping gets reached.
        if proxy is None:
            # ProxyBroker package might actually put None in when there are no
            # more proxies in which case this can cause issues.
            self.log.warning(f"{self.__class__.__name__} is Stopping")
            await self.stop()
            return

        # Original Portion
        else:
            if (proxy.stat['requests'] >= self._min_req_proxy or
                    proxy.error_rate > self._max_error_rate or
                    proxy.avg_resp_time > self._max_resp_time):
                self.log.debug('%s:%d removed from proxy pool' % (proxy.host, proxy.port))
            else:
                self.log.debug('Putting Proxy in Pool', extra={'proxy': proxy})
                heapq.heappush(self._pool, (proxy.priority, proxy))
            self.log.debug('%s:%d stat: %s' % (proxy.host, proxy.port, proxy.stat))
