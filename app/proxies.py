from __future__ import absolute_import

import time

import asyncio
from proxybroker import Broker

from app.logging import AppLogger
from app.lib.models import Proxy


log = AppLogger('Proxies')


async def proxy_broker(proxies, loop):
    log.notice('Starting Broker')
    broker = Broker(proxies, timeout=8, max_conn=100, max_tries=3)
    while True:
        try:
            await broker.find(
                types=['HTTP', 'HTTPS'],
                post=True,
            )
        # Proxy Broker will get hung up on tasks as we are trying to shut down
        # if we do not do this.
        except RuntimeError:
            break


async def test_proxies(proxies, loop):
    log.notice('Starting Tester')
    while True:
        log.info("Trying and waiting for proxy...")
        proxy = await proxies.get()
        log.info(
            f"Average Response Time: {proxy.avg_resp_time} \n"
            f"Error Rate: {proxy.error_rate} \n"
            f"Is Working: {proxy.is_working} \n"
        )


class proxy_handler(object):

    def __init__(self, config, proxies):
        self.config = config
        self.proxies = proxies
        self.good = []
        self.backpocket = []
        self.handled = asyncio.Queue()

    async def get_best(self):
        # We could run into race conditions here - we may want to have a try
        # except.
        if len(self.good) != 0:
            # Don't want to immediately put proxies back in because we will
            # hit too many requests with same proxy, we shoudl eventually
            # start using a proxy list.
            return self.good[0]
            proxy = self.good.pop(0)
            self.backpocket.append(proxy)
            return proxy

        return await self.handled.get()

    async def note_bad(self, proxy):
        if proxy in self.good:
            self.good.remove(proxy)
        if proxy in self.backpocket:
            self.backpocket.remove(proxy)

    async def add_good(self, proxy):
        if proxy not in self.good:
            self.good.append(proxy)

    async def produce_proxies(self):
        """
        We are going to use this to better control the flow of proxies into the
        system.

        We don't need them to be funneling through at super fast speeds, and we
        also may want to validate them in some way before providing them to the
        consumers.
        """
        log.notice('Starting...')

        def validate_proxy(proxy):
            if not proxy.is_working:
                return False
            if proxy.avg_resp_time >= 2.0 or proxy.error_rate > 0.5:
                return False
            return True

        while True:
            proxy = await self.proxies.get()
            if validate_proxy(proxy):
                if self.config.proxy_sleep:
                    time.sleep(self.config.proxy_sleep)

                proxy = Proxy(port=proxy.port, host=proxy.host)
                self.handled.put_nowait(proxy)
