from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.config import config

from instattack.lib.utils import start_and_stop

from instattack.app.exceptions import find_request_error, find_response_error
from instattack.app.mixins import LoggerMixin
from instattack.app.proxies import ProxyBroker


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
        log = self.create_logger('close_scheduler')
        await log.start('Closing Scheduler')
        await self.scheduler.close()
        await log.complete('Scheduler Closed')


class ProxyHandler(Handler):

    __name__ = "Proxy Handler"

    def __init__(self, loop, start_event=None, stop_event=None):
        """
        [x] TODO:
        ---------
        We need to use the stop event to stop the broker just in case an authenticated
        result is found.

        What would be really cool would be if we could pass in our custom pool
        directly so that the broker popoulated that queue with the proxies.
        """
        super(ProxyHandler, self).__init__(loop, start_event=start_event,
            stop_event=stop_event)
        self.broker = ProxyBroker(loop)

    async def stop(self):
        if self.broker._started:
            self.broker.stop()

    async def run(self):
        """
        Retrieves proxies from the queue that is populated from the Broker and
        then puts these proxies in the prioritized heapq pool.

        Prepopulates proxies if the flag is set to put proxies that we previously
        saved into the pool.

        [x] TODO:
        ---------
        We are eventually going to need the relationship between prepopulation
        and collection to be more dynamic and adjust, and collection to trigger
        if we are running low on proxies.
        """
        log = self.create_logger('start')
        await log.start(f'Starting {self.__name__}')

        try:
            await log.debug('Prepopulating Proxy Pool...')
            await self.pool.prepopulate()
        except Exception as e:
            raise e

        if config['pool']['collect']:
            # Pool will set start event when it starts collecting proxies.
            await self.pool.collect()
        else:
            if self.start_event.is_set():
                raise RuntimeError('Start Event Already Set')

            self.start_event.set()
            await log.info('Setting Start Event', extra={
                'other': 'Proxy Pool Prepopulated'
            })


class RequestHandler(Handler):

    def __init__(self, loop, proxy_handler, **kwargs):
        super(RequestHandler, self).__init__(loop, **kwargs)

        self.proxy_handler = proxy_handler
        self.num_completed = 0
        self.proxies_to_save = []

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

    def connector(self, loop):
        return aiohttp.TCPConnector(
            loop=loop,
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
