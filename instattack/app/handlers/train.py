import aiohttp
import asyncio
import progressbar

from instattack.config import config

from instattack.lib.utils import limit_as_completed, percentage

from instattack.app.exceptions import PoolNoProxyError
from instattack.app.proxies import SimpleProxyPool

from .proxies import SimpleProxyHandler
from .base import AbstractRequestHandler
from .requests import train_request


__all__ = (
    'TrainHandler',
)


class TrainHandler(AbstractRequestHandler):

    __name__ = 'Train Handler'
    __proxy_handler__ = SimpleProxyHandler
    __proxy_pool__ = SimpleProxyPool

    async def train(self, limit=None):
        try:
            results = await asyncio.gather(
                self._train(limit=limit),
                self.proxy_handler.run(limit=limit),
            )
        except Exception as e:
            await self.finish()
            await self.proxy_handler.stop()
            raise e
        else:
            # We might not need to stop proxy handler?
            await self.proxy_handler.stop()
            return results[0]

    async def _train(self, limit=None):
        # Currently, no results
        results = await self.request(limit=limit)
        await self.finish()
        return results

    async def train_request(self, session, proxy):
        return await train_request(
            loop=self.loop,
            session=session,
            proxy=proxy,
            on_proxy_success=self.on_proxy_success,
            on_proxy_request_error=self.on_proxy_request_error,
            on_proxy_response_error=self.on_proxy_response_error,
        )

    async def generate_attempts_for_proxies(self, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            proxy = await self.proxy_handler.pool.get()
            if not proxy:
                raise PoolNoProxyError()
            yield self.train_request(session, proxy)

    async def request(self, limit=None):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        progressbar.streams.wrap_stdout()
        progressbar.streams.wrap_stderr()

        log = self.create_logger('login')

        log.debug('Waiting on Start Event')
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:

            bar = progressbar.ProgressBar(max_value=limit or progressbar.UnknownLength)

            count = 0
            async for result, current_attempts, current_tasks in limit_as_completed(
                coros=self.generate_attempts_for_proxies(session),
                batch_size=config['proxies']['train']['batch_size']
            ):
                count += 1
                bar.update(count)

        await asyncio.sleep(0)
        await self.close_scheduler()
