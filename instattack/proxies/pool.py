from __future__ import absolute_import

import heapq
import stopit
from urllib.parse import urlparse

from proxybroker import ProxyPool

from instattack import settings
from instattack import exceptions
from instattack.handlers import MethodObj

from .exceptions import ProxyPoolException, PoolNoProxyError
from .utils import read_proxies, filter_proxies, write_proxies
from .models import Proxy


__all__ = ('CustomProxyPool', )


class CustomProxyPool(ProxyPool, MethodObj):
    """
    Imports and gives proxies from queue on demand.

    Overridden because of weird error referenced:

    Weird error from ProxyBroker that makes no sense...
    TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'

    We also want the ability to put None in the queue so that we can stop the
    consumers.
    """
    __subname__ = "Proxy Pool"

    def __init__(
        self,
        proxies,
        method=None,
        timeout=None,
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
        self._timeout = timeout

        # We need to use this so that we can tell the difference when the found
        # proxy is None as being intentionally put in the queue to stop the
        # consumer or because there are no more proxies left from the Broker.
        self._stopped = False
        self._setup(method=method)

    @property
    def scheme(self):
        scheme = urlparse(settings.URLS[self.method]).scheme
        return scheme.upper()

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        read_proxy_list = []
        with self.log.start_and_done(f'Prepopulating {self.__name__}'):
            proxies = read_proxies(method=self.method)
            for proxy in filter_proxies(
                proxies,
                max_error_rate=self._max_error_rate,
                max_resp_time=self._max_resp_time
            ):
                if proxy in read_proxy_list:
                    # This isn't totally necessary since we check for duplicates
                    # in the .put() method, but it helps us know where they
                    # are coming from if we see them.
                    self.log.warning('Found Duplicate Saved Proxy', extra={'proxy': proxy})
                else:
                    read_proxy_list.append(proxy)
                    await self.put(proxy)
        return read_proxy_list

    async def start(self, loop):
        """
        If the proxy that is retrieved from the self._proxies Queue is None,
        but self._stopped is set, that means it was intentionally put in to shut
        down the pool.

        Otherwise, if the proxy is None and self._stopped is not set, than this
        indicates that the ProxyBroker has reached its limit, so we raise the
        NoProxyError.
        """
        await self.prepopulate(loop)

        while True:
            proxy = await self._proxies.get()
            # self._proxies.task_done()  # In Original Code

            if not proxy:
                if not self._stopped:
                    raise PoolNoProxyError()
                else:
                    # This block only gets reached after the self.put method is
                    # called with a proxy value of None, which triggers the self.stop()
                    # method.  That means that all we have to do here is exit
                    # the loop.
                    break

            elif self.scheme not in proxy.schemes:
                self.log.debug('Expected Scheme not in Proxy Schemes', extra={'proxy': proxy})
                await self.put(proxy)
            else:
                self.log.debug('Queueing Proxy', extra={'proxy': proxy})
                await self.put(proxy)
                # self.log.debug('Returning Proxy', extra={'proxy': proxy})
                # return proxy

    async def stop(self):
        with self.log.start_and_done(f"Stopping {self.__name__}"):
            self._stopped = True
            self._pool = []
            await self._proxies.put(None)

    async def get(self, ):

        if self._stopped:
            raise ProxyPoolException("Cannot get proxy from stopped pool.")

        with stopit.SignalTimeout(self._timeout) as timeout_mgr:
            for priority, proxy in self._pool:
                if self.scheme in proxy.schemes:
                    chosen = proxy
                    self._pool.remove((proxy.priority, proxy))
                    break
            else:
                chosen = await self._import()

        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise exceptions.InternalTimeout(
                self._timeout, f"Proxy from {self.pool.__name__}")
        return chosen

    async def _import(self):
        while True:
            proxy = await self._proxies.get()
            self._proxies.task_done()
            if not proxy:
                raise PoolNoProxyError('No more available proxies')
            elif self.scheme not in proxy.schemes:
                await self.put(proxy)
            else:
                return Proxy.from_proxybroker(proxy)

    async def put(self, proxy):
        """
        TODO:
        -----
        We might want to start min_req_per_proxy to a higher level since we
        are controlling how often they are used to avoid max request errors!!!

        We can also prioritize by number of requests to avoid max request errors
        """
        # Overridden Portion - We might want to put None in the consumed proxies,
        # so that the block that logs that the pool is stoping gets reached.
        if proxy is None:
            # ProxyBroker package might actually put None in when there are no
            # more proxies in which case this can cause issues.
            self.log.warning(f"{self.__class__.__name__} is Stopping")
            await self.stop()
            return

        if not isinstance(proxy, Proxy):
            proxy = Proxy.from_proxybroker(proxy)

        if (proxy.priority, proxy) in self._pool:
            self.log.warning('Found Duplicate Proxy in Pool', extra={'proxy': proxy})

        if (proxy.num_requests >= self._min_req_proxy and
                (proxy.error_rate > self._max_error_rate or
                    proxy.avg_resp_time > self._max_resp_time)):
            self.log.debug('%s:%d removed from proxy pool' % (proxy.host, proxy.port))
        else:
            try:
                heapq.heappush(self._pool, (proxy.priority, proxy))
            except TypeError as e:
                # TODO: Fix This - Might not be applicable anymore with new setup.
                # Weird error from ProxyBroker that makes no sense...
                # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
                self.log.warning(e)
                self._pool.append((proxy.priority, proxy))

        self.log.debug('%s:%d stat: %s' % (proxy.host, proxy.port, proxy.stat))
