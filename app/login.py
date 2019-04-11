from __future__ import absolute_import

import collections
import logging

import aiohttp
import asyncio

from app import settings
from app.lib import exceptions
from app.lib.utils import AsyncTaskManager, auto_logger, format_proxy
from app.lib.models import InstagramResult

from .requests import request_handler


LoginTaskContext = collections.namedtuple('LoginTaskContext',
    'name proxy token password')


class login_handler(request_handler):

    # We are going to have to adjust these probably - it might take more than
    # 10 attempts to retrieve a result if we have bad proxies.
    # This might not be as appropriate for async cases.
    ATTEMPT_LIMIT = settings.LOGIN_ATTEMPT_LIMIT
    CONNECTOR_KEEP_ALIVE_TIMEOUT = 3.0

    def __init__(self, config, global_stop_event, queues):
        super(login_handler, self).__init__(config, global_stop_event, queues)
        self.user = self.config.user

    def login_data(self, password):
        return {
            'username': self.user.username,
            'password': password
        }

    def _headers(self, token):
        headers = super(login_handler, self)._headers()
        headers['x-csrftoken'] = token
        return headers

    def _log_context(self, context, **kwargs):
        context = {
            'task': context.name,
            'proxy': context.proxy,
            'token': context.token,
            'password': context.password,
        }
        context.update(**kwargs)
        return context

    async def task_generator(self, log, password, **context):
        index = 0
        while not self.stop_event.is_set() and index < self.ATTEMPT_LIMIT:
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

    @property
    def connector(self):
        """
        TCPConnector
        -------------
        keepalive_timeout (float) – timeout for connection reusing aftet
            releasing
        limit_per_host (int) – limit simultaneous connections to the same
            endpoint (default is 0)
        """
        return aiohttp.TCPConnector(
            ssl=False,
            keepalive_timeout=self.CONNECTOR_KEEP_ALIVE_TIMEOUT,
            enable_cleanup_closed=True,
        )

    @property
    def timeout(self):
        return aiohttp.ClientTimeout(
            total=settings.DEFAULT_LOGIN_FETCH_TIME
        )

    async def _get_result_from_response(self, response):
        try:
            result = await response.json()
        except ValueError:
            raise exceptions.ResultNotInResponse()
        else:
            return InstagramResult.from_dict(result)

    async def _handle_client_response(self, response, context, log):
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
                return await self._get_result_from_response(response)
            else:
                response.raise_for_status()
        else:
            try:
                return await self._get_result_from_response(response)
            except exceptions.ResultNotInResponse as e:
                raise exceptions.FatalException(
                    "Unexpected behavior, result should be in response.",
                    extra=self._log_context(context, response=response)
                )

    async def _handle_parsed_result(self, result, context, log):
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

    async def request(self, session, context, retry=1):
        """
        Do not want to automatically raise for status because we can have
        a 400 error but enough info in response to authenticate.

        Also, once response.raise_for_status() is called, we cannot access
        the response.json().
        """
        # Autologger not working because of keyword argument
        log = logging.getLogger('Login')
        self.log_post_request(context, log, retry=retry)

        try:
            async with session.post(
                settings.INSTAGRAM_LOGIN_URL,
                headers=self._headers(context.token),
                data=self.login_data(context.password),
                timeout=settings.DEFAULT_LOGIN_FETCH_TIME,
                proxy=format_proxy(context.proxy)
            ) as response:
                # Only reason to log these errors here is to provide the response
                # object
                try:
                    result = await self._handle_client_response(response, context, log)
                    result = await self._handle_parsed_result(result, context, log)

                except exceptions.ResultNotInResponse as e:
                    log.error(e, extra=self._log_context(context, response=response))

                except exceptions.InstagramResultError as e:
                    log.error(e, extra=self._log_context(context, response=response))

                else:
                    if not result:
                        raise exceptions.FatalException("Result should not be None here.")
                    self.queues.proxies.good.put_nowait(context.proxy)

                    return result

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError,
                asyncio.TimeoutError) as e:
            retry += 1

            # We probably want to lower this number
            if retry < 5:
                # Session should still be alive.
                await asyncio.sleep(1)
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra=self._log_context(context))
                return None

            # Session should still be alive.
            await asyncio.sleep(1)
            return await self.request(session, context, retry=retry)

        except aiohttp.ClientError as e:
            log.error(e, extra=self._log_context(context))

        except Exception as e:
            raise exceptions.FatalException(f'Uncaught Exception: {str(e)}')

    @auto_logger("Sync Login")
    async def login_synchronously(self, token, password, log):

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            async for context in self.task_generator(log, password, token=token):
                log.debug("Submitting Task", extra={
                    'task': context.name
                })
                if not self.stop_event.is_set():
                    result = await self.request(session, context)
                    if result:
                        if result.has_error:
                            log.warning(result.error_message, extra={
                                'token': token,
                                'password': password,
                                'task': context.name,
                            })
                        else:
                            self.queues.proxies.good.put_nowait(context.proxy)
                            if result.conclusive:
                                self.stop_event.set()
                                return result

    @auto_logger("Async Login")
    async def login_asynchronously(self, token, password, log):
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

        IMPORTANT
        _________
        What we should do is start off with a minimum of like 3 requests, if none
        of those succeed, then incrementally add one more one more etc. - the issue
        is if we do not get a valid response for any of the 5 requests we set.
        """
        # ClientSession should remain open in between futures, so looping over
        # the context within the session shouldn't make a difference.
        async with AsyncTaskManager(self.stop_event, log=log) as task_manager:
            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            ) as session:
                async for context in self.task_generator(log, password, token=token):
                    log.debug("Submitting Task", extra={
                        'task': context.name
                    })
                    task = asyncio.create_task(self.request(session, context))
                    task_manager.add(task)

                for future in asyncio.as_completed(task_manager.tasks, timeout=None):
                    # Result can be None if there was a request error or the result
                    # was invalid, but if the result is present - it is guaranteed to
                    # be conclusive.
                    try:
                        result = await future
                    except asyncio.CancelledError:
                        continue
                    else:
                        if result:
                            if not result.conclusive:
                                raise exceptions.FatalException("Result should be conslusive.")

                            await task_manager.stop()
                            return result

        async def login(self, token, password):
            if self.config.sync:
                return await self.login_synchronously(token, password)
            return await self.login_asynchronously(token, password)
