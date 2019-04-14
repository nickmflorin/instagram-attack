from __future__ import absolute_import

import asyncio
import time
import logbook

from app.lib.models import Proxy


__all__ = ('proxy_handler', )


log = logbook.Logger(__file__)


class proxy_handler(object):

    def __init__(self, config, global_stop_event, generated):
        self.config = config
        self.global_stop_event = global_stop_event

        self.generated = generated
        self.good = asyncio.Queue()
        self.handled = asyncio.Queue()

    async def get_best(self):
        # We could run into race conditions here - we may want to have a try
        # except.
        if not self.good.empty():
            # Don't want to immediately put proxies back in because we will
            # hit too many requests with same proxy, we shoudl eventually
            # start using a proxy list.
            proxy = await self.good.get()
            # self.good.put_nowait(proxy)
            return proxy
        return await self.handled.get()

    async def produce_proxies(self):
        """
        We are going to use this to better control the flow of proxies into the
        system.

        We don't need them to be funneling through at super fast speeds, and we
        also may want to validate them in some way before providing them to the
        consumers.
        """
        log.notice('Starting...')

        while not self.global_stop_event.is_set():
            proxy = await self.generated.get()
            if proxy:
                if self.config.proxysleep:
                    time.sleep(self.config.proxysleep)

                proxy = Proxy(port=proxy.port, host=proxy.host)
                self.handled.put_nowait(proxy)
            else:
                log.critical('No New Proxies')
