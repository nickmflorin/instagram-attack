from __future__ import absolute_import

import time
import subprocess
import sys

import asyncio
from proxybroker import Broker
from proxybroker.server import Server

from app import settings
from app.lib.utils import find_pids_on_port
from app.logging import AppLogger


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


BROKERS = {
    'GET': TokenBroker,
    'POST': LoginBroker,
}
