from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.config import config

from instattack.lib import logger
from instattack.lib.utils import start_and_stop

from instattack.app.exceptions import translate_error


log = logger.get(__name__)


class Handler(object):

    SCHEDULER_LIMIT = 1000

    def __init__(self, loop, start_event=None):

        self.loop = loop
        self.start_event = start_event

        self.scheduler = self.loop.run_until_complete(aiojobs.create_scheduler(
            limit=self.SCHEDULER_LIMIT,
        ))

    async def schedule_task(self, coro):
        await self.scheduler.spawn(coro)

    async def close_scheduler(self):
        with start_and_stop('Closing Scheduler'):
            await self.scheduler.close()


class AbstractRequestHandler(Handler):

    __proxy_manager__ = None
    __proxy_pool__ = None
    __client__ = None

    def __init__(self, loop, **kwargs):
        super(AbstractRequestHandler, self).__init__(loop, **kwargs)

        self.num_completed = 0

        self.proxies_to_save = []
        self.saved_proxies = []

        self.start_event = asyncio.Event()
        self.stop_event = asyncio.Event()

        self.proxy_manager = self.__proxy_manager__(
            loop,
            pool_cls=self.__proxy_pool__,
            start_event=self.start_event,
        )

        self.client = self.__client__(
            self.loop,
            on_error=self.on_proxy_error,
            on_success=self.on_proxy_success
        )

    @property
    def connector(self):
        return aiohttp.TCPConnector(
            loop=self.loop,
            ssl=False,
            force_close=True,
            limit=config['connection']['connection_limit'],
            limit_per_host=config['connection']['limit_per_host'],
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=config['connection']['connection_timeout']
        )

    async def save_proxy(self, proxy):
        self.saved_proxies.append(proxy)
        await proxy.save()

    async def finish(self):
        """
        [x] TODO:
        --------
        Figure out a way to guarantee that this always gets run even if we hit
        some type of error.
        """
        if config['proxies']['save_method'] == 'live':
            if len(self.saved_proxies) != 0:
                # Still Use Context Manager Just for Style Purposes - Need Another
                # Solution to Keep Things Consistent
                with start_and_stop(f"Saved {len(self.saved_proxies)} Proxies"):
                    pass
        else:
            if len(self.proxies_to_save) != 0:
                with start_and_stop(f"Saving {len(self.proxies_to_save)} Proxies"):
                    tasks = [proxy.save() for proxy in self.proxies_to_save]
                    await asyncio.gather(*tasks)

        await self.close_scheduler()

    async def on_proxy_error(self, proxy, e):
        err = translate_error(e)
        if not err:
            raise e

        assert not type(e) is str
        await self.proxy_manager.on_proxy_error(proxy, err)

        if config['proxies']['save_method'] == 'live':
            await self.schedule_task(proxy.save())
        else:
            # Do we need to find and replace here?
            if proxy not in self.proxies_to_save:
                self.proxies_to_save.append(proxy)

    async def on_proxy_success(self, proxy):

        await self.proxy_manager.on_proxy_success(proxy)

        if config['proxies']['save_method'] == 'live':
            await self.schedule_task(self.save_proxy(proxy))
        else:
            # Do we need to find and replace here?
            if proxy not in self.proxies_to_save:
                self.proxies_to_save.append(proxy)
