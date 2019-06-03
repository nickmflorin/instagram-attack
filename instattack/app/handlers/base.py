from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.config import config

from instattack.lib.utils import start_and_stop

from instattack.app.exceptions import find_request_error, find_response_error
from instattack.app.mixins import LoggerMixin


class Handler(LoggerMixin):

    SCHEDULER_LIMIT = 1000

    def __init__(self, loop, start_event=None, stop_event=None):

        self.loop = loop
        self.start_event = start_event
        self.stop_event = stop_event

        self.scheduler = self.loop.run_until_complete(aiojobs.create_scheduler(
            limit=self.SCHEDULER_LIMIT,
        ))

    async def schedule_task(self, coro):
        await self.scheduler.spawn(coro)

    async def close_scheduler(self):
        with start_and_stop('Closing Scheduler'):
            await self.scheduler.close()


class AbstractRequestHandler(Handler):

    __proxy_handler__ = None
    __proxy_pool__ = None

    def __init__(self, loop, **kwargs):
        super(AbstractRequestHandler, self).__init__(loop, **kwargs)

        self.num_completed = 0
        self.proxies_to_save = []

        self.start_event = asyncio.Event()
        self.stop_event = asyncio.Event()

        self.proxy_handler = self.__proxy_handler__(
            loop,
            pool_cls=self.__proxy_pool__,
            start_event=self.start_event,
            stop_event=self.stop_event,
        )

    async def finish(self):
        """
        [x] TODO:
        --------
        Figure out a way to guarantee that this always gets run even if we hit
        some type of error.
        """
        if config['proxies']['save_method'] == 'end':
            with start_and_stop(f"Saving {len(self.proxies_to_save)} Proxies"):
                tasks = [proxy.save() for proxy in self.proxies_to_save]
                await asyncio.gather(*tasks)

    @property
    def connector(self):
        return aiohttp.TCPConnector(
            loop=self.loop,
            ssl=False,
            force_close=True,
            limit=config['connection']['limit'],
            limit_per_host=config['connection']['limit_per_host'],
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=config['connection']['timeout']
        )

    async def on_proxy_request_error(self, proxy, e):
        err = find_request_error(e)
        if not err:
            raise e

        await self.proxy_handler.pool.on_proxy_request_error(proxy, err)

        if config['proxies']['save_method'] == 'live':
            await self.schedule_task(proxy.save())
        else:
            # Do we need to find and replace here?
            if proxy not in self.proxies_to_save:
                self.proxies_to_save.append(proxy)

    async def on_proxy_response_error(self, proxy, e):
        err = find_response_error(e)
        if not err:
            raise e

        await self.proxy_handler.pool.on_proxy_response_error(proxy, err)

        if config['proxies']['save_method'] == 'live':
            await self.schedule_task(proxy.save())
        else:
            # Do we need to find and replace here?
            if proxy not in self.proxies_to_save:
                self.proxies_to_save.append(proxy)

    async def on_proxy_success(self, proxy):
        await self.proxy_handler.pool.on_proxy_success(proxy)

        if config['proxies']['save_method'] == 'conclusively':
            # Do we need to find and replace here?
            if proxy not in self.proxies_to_save:
                self.proxies_to_save.append(proxy)
        else:
            await self.schedule_task(proxy.save())
