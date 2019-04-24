from __future__ import absolute_import

import asyncio

from datetime import datetime
from urllib.parse import urlparse

import stopit

from instattack import exceptions
from instattack.conf import settings

from instattack.proxies import BROKERS
from instattack.proxies.server import CustomProxyPool
from instattack.proxies.utils import read_proxies
from instattack.proxies.models import Proxy

from .base import Handler


class ProxyHandler(Handler):
    """
    TODO:
    -----

    This could be cleaned up a bit, with the validation in particular.
    It might be worthwhile looking into whether or not we can subclass the
    asyncio.Queue() so we don't have to have the methods on this handler and
    pass the handler around.

    The logic in here definitely needs to be looked at and cleaned up, particularly
    in terms of the order we are validating and when we are validating the proxies.
    """
    __name__ = 'Proxy Handler'

    def __init__(self, user, method='GET', **kwargs):
        kwargs['__name__'] = f'{method} {self.__name__}'
        super(ProxyHandler, self).__init__(user, **kwargs)

        self.method = method

        # TODO:  Once we subclass CustomProxyPool to correctly use our proxy
        # model instead of theirs, we don't need separate queues for the proxies
        # that we read from .txt file and filter out from the server and the
        # proxies that are read from the server.

        # Proxies we read from .txt files on prepopulate and then proxies we
        # get from server during live run.
        self.proxies = asyncio.Queue()

        # We don't really access self.served_proxies, it's just so that there
        # is a queue that the proxy pool can store the proxies in.
        self.served_proxies = asyncio.Queue()
        self.server = self.broker_cls(self.served_proxies)
        self._server_running = False
        self.pool = CustomProxyPool(self.served_proxies)

    @property
    def broker_cls(self):
        return BROKERS[self.method]

    @property
    def scheme(self):
        return urlparse(settings.URLS[self.method]).scheme

    async def put(self, proxy, update_time=True):
        if proxy and update_time:
            proxy.last_used = datetime.now()
        await self.proxies.put(proxy)

    async def put_nowait(self, proxy, update_time=True):
        if proxy and update_time:
            proxy.last_used = datetime.now()
        await self.proxies.put_nowait(proxy)

    async def validate_proxy(self, proxy):
        if not proxy.last_used:
            return True
        else:
            # TODO: Move this value to settings.
            if proxy.time_since_used() >= 10:
                return True
            else:
                await self.proxies.put(proxy)
                return False

    async def get_from_queue(self):
        while True:
            proxy = await self.proxies.get()

            # Emit None to Alert Consumer to Stop Listening
            if proxy is None:
                break

            # Should we maybe check these verifications before we put the
            # proxy in the queue to begin with?
            valid = await self.validate_proxy(proxy)
            if valid:
                return proxy

    async def get(self):
        """
        TODO
        ----
        Move the allowed timeout for finding a given proxy that satisfies
        reauirements to settings.

        We will set the timeout very high right now, because it sometimes takes
        awhile for the proxies to build up - setting this low causes it to fail
        during early stages of login attempts.
        """
        with stopit.SignalTimeout(50) as timeout_mgr:
            proxy = await self.get_from_queue()
            self.log.info('THE CHECK BELOW IS NOT WORKING, NO PROXY HAS TIME SINCE USED')
            if proxy:
                if proxy.time_since_used():
                    # TODO: Make this debug level once we are more comfortable
                    # with operation.
                    self.log.info('Returning Proxy %s Used %s Seconds Ago' %
                        (proxy.host, proxy.time_since_used()))

        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise exceptions.InternalTimeout("Timed out waiting for a valid proxy.")

        return proxy

    async def start_server(self, loop):
        with self.log.start_and_done(f'Starting {self.method} Server'):
            self.server.find()
        self._server_running = True

    async def stop_server(self, loop):
        # Stopping server can be done outside of main event loop but starting
        # it must be done at the top level in loop.run_until_complete().
        with self.log.start_and_done(f'Stopping {self.method} Server'):
            self.server.stop()
        self._server_running = False

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """

        # Make max_error_rate and max_resp_time for proxies configurable, and if
        # they are set, than we can filter the proxies we read by those values.
        with self.log.start_and_done(f'Prepopulating {self.method} Proxies'):
            proxies = read_proxies(method=self.method, order_by='avg_resp_time')
            for proxy in proxies:
                await self.put(proxy, update_time=False)

    async def produce(self, loop):
        """
        Stop event is not needed for the GET case, where we are finding a token,
        because we can trigger the generator to stop by putting None in the queue.

        On the other hand, if we notice that a result is authenticated, we need
        the stop event to stop handlers mid queue.

        TODO
        -----
        Stop event should not be needed if we can break when the found proxy
        is None.  That is why we override the ProxyPool, to allow us to put
        None in there.

        However, this might also be a case where there are actually no more
        proxies from the server, which would otherwise raise a NoProxyError.

        We may run into issues with that down the line.
        """
        with self.log.start_and_done(f'Producing {self.method} Proxies'):
            while True:
                try:
                    self.log.debug('Waiting on Proxy...')
                    proxy = await self.pool.get(scheme=self.scheme)

                    # See docstring about None value.
                    if proxy is None:
                        self.log.debug('None in Pool Indicated Stop')
                        self.put_nowait(None)
                        self.log.debug('Put None in Pool...')
                        break

                # Weird error from ProxyBroker that makes no sense...
                # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
                except TypeError as e:
                    self.log.warning(e)

                else:
                    proxy = Proxy.from_broker_proxy(proxy)
                    # TODO: Move these values to settings.
                    if proxy.error_rate <= 0.5 and proxy.avg_resp_time <= 5.0:
                        # Should we maybe check other proxy verifications before we put the
                        # proxy in the queue to begin with?
                        await self.put(proxy, update_time=False)

            await self.stop_server(loop)
