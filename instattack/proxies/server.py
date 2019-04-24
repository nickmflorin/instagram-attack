from __future__ import absolute_import

import heapq
import time
import subprocess
import sys

import asyncio
from proxybroker import Broker, ProxyPool
from proxybroker.errors import NoProxyError
from proxybroker.server import Server

from instattack.conf import settings
from instattack.logger import AppLogger

from .utils import find_pids_on_port


log = AppLogger(__file__)


__all__ = ('TokenBroker', 'LoginBroker', )


def kill_processes_on_port(port):
    """
    Because of executor, or maybe other reasons, we are not getting OSError
    when trying to start subprocess on same port.  Leading to many processes
    on the same port.

    Instead, we will just kill all processes on the port ahead of time.

    Not currently being used but we may decide to use again in the future.
    """
    for pid in find_pids_on_port(port):
        log.warning(f'Found PID {pid} Running on Port {port}')
        log.info(f'Killing PID {pid}')
        subprocess.Popen(['kill', '-9', "%s" % pid], stdout=sys.stdout)
        log.notice(f'Successfully Killed PID {pid}')


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


class CustomServer(Server):
    """
    Override proxybroker Server since their version stops the main event loop
    when the server shuts down, which means it is impossible to have multiple
    servers run in the same asyncio program (one for GET and one for POST
    requests).

    Not currently being used but we may decide to use again in the future.
    """

    def start(self):
        log.notice(f'Starting {self.__name__}')
        kill_processes_on_port(self.port)
        time.sleep(1)
        return super(CustomServer, self).start()

    def stop(self):
        log.warning(f'Stopping {self.__name__}')
        if not self._server:
            return

        for conn in self._connections:
            if not conn.done():
                conn.cancel()
        self._server.close()

        if not self._loop.is_running():
            self._loop.run_until_complete(self._server.wait_closed())
            # Time to close the running futures in self._connections
            self._loop.run_until_complete(asyncio.sleep(0.5))

        self._server = None
        log.info(f'{self.__name__} is stopped')


class TokenProxyServer(CustomServer):

    __name__ = 'Token Proxy Server'


class LoginServer(CustomServer):

    __name__ = 'Login Proxy Server'


class CustomBroker(Broker):
    """
    Overridden to allow custom server to be used and convenience settings
    to be implemented directly from the settings module.
    """

    def __init__(self, *args, **kwargs):
        return super(CustomBroker, self).__init__(
            *args, **self.__broker_settings__,
        )

    def find(self):
        return super(CustomBroker, self).find(**self.__find_settings__)

    def serve(self):

        self._server = self.__server_cls__(
            proxies=self._proxies,
            timeout=self._timeout,
            loop=self._loop,
            **self.__serve_settings__
        )

        self._server.start()

        task = asyncio.ensure_future(self.find())
        self._all_tasks.append(task)


class TokenBroker(CustomBroker):

    __server_cls__ = TokenProxyServer
    __broker_settings__ = settings.BROKER_CONFIG['GET']
    __find_settings__ = settings.BROKER_CONFIG['FIND']['GET']
    __serve_settings__ = settings.BROKER_CONFIG['FIND']['GET']


class LoginBroker(CustomBroker):

    __server_cls__ = LoginServer
    __broker_settings__ = settings.BROKER_CONFIG['POST']
    __find_settings__ = settings.BROKER_CONFIG['FIND']['POST']
    __serve_settings__ = settings.BROKER_CONFIG['SERVE']['POST']
