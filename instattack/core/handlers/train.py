import aiohttp
import asyncio

from instattack.config import config

from instattack.lib import logger
from instattack.lib.utils import limit_as_completed, progress

from instattack.core.proxies import SimpleProxyPool, SimpleProxyManager

from .base import AbstractRequestHandler
from .client import train_client


__all__ = (
    'TrainHandler',
)

log = logger.get(__name__, 'Train Handler')


class TrainHandler(AbstractRequestHandler):

    __name__ = 'Train Handler'
    __proxy_manager__ = SimpleProxyManager
    __proxy_pool__ = SimpleProxyPool
    __client__ = train_client

    async def train(self, limit=None, confirmed=False):
        try:
            results = await asyncio.gather(
                self._train(limit=limit),
                self.proxy_manager.start(limit=limit, confirmed=confirmed),
            )
        except Exception as e:
            await self.finish()
            await self.proxy_manager.stop()
            raise e
        else:
            # We might not need to stop proxy handler?
            await self.proxy_manager.stop()
            return results[0]

    async def _train(self, limit=None):
        # Currently, no results
        results = await self.request(limit=limit)
        await self.finish()
        return results

    async def generate_attempts_for_proxies(self, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.

        [!] IMPORTANT
        -------------
        Do not raise a PoolNoProxyError when training because we expect that
        to happen at some point, since we are using at most the number of current
        proxies we have.
        """
        while True:
            proxy = await self.proxy_manager.get()
            if proxy:
                yield self.client.request(session, proxy)

    async def request(self, limit=None):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log.debug('Waiting on Start Event')
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:

            gen = self.generate_attempts_for_proxies(session)
            async for fut in limit_as_completed(gen, batch_size=config['proxies']['train']['batch_size']):  # noqa
                if fut.exception():
                    raise fut.exception()

                result, num_tries = fut.result()
                log.debug(result)

                self.num_completed += 1
                pct = progress(self.num_completed, self.proxy_manager.original_num_proxies)
                log.info(pct)

        await asyncio.sleep(0)
