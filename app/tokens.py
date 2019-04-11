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
    auto_logger, format_proxy, get_token_from_response, AsyncTaskManager)

from .requests import request_handler

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


class token_handler(request_handler):

    # We are going to have to adjust these probably - it might take more than
    # 10 attempts to retrieve a result if we have bad proxies.
    ATTEMPT_LIMIT = settings.TOKEN_ATTEMPT_LIMIT

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    def _log_context(self, context, **kwargs):
        context = {
            'task': context.name,
            'proxy': context.proxy,
        }
        context.update(**kwargs)
        return context

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
            total=settings.DEFAULT_TOKEN_FETCH_TIME
        )

    async def request(self, session, context, retry=1):

        # Autologger not working because of keyword argument
        log = logging.getLogger('Token Task')
        self.log_get_request(context, log, retry=retry)

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
                    log.critical(token)
                except exceptions.TokenNotInResponse as e:
                    log.warning(e, extra=self._log_context(context, response=response))
                    return None
                else:
                    self.queues.proxies.good.put_nowait(context.proxy)
                    return token

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            log.warning(e, extra=self._log_context(context))
            retry += 1

            # We probably want to lower this number
            if retry < 5:
                # Session should still be alive.
                await asyncio.sleep(1)
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra=self._log_context(context))
                return None

        except aiohttp.ClientError as e:
            log.error(e, extra=self._log_context(context))

        except asyncio.CancelledError:
            return None

        except Exception as e:
            raise exceptions.FatalException(
                f'Uncaught Exception: {str(e)}', extra=self._log_context(context))

    @auto_logger("Getting Token")
    async def __call__(self, log):
        """
        Asyncio Docs:

        asyncio.as_completed

            Run awaitable objects in the aws set concurrently. Return an iterator
            of Future objects. Each Future object returned represents the earliest
            result from the set of the remaining awaitables.

            Raises asyncio.TimeoutError if the timeout occurs before all Futures are done.
        """
        async with AsyncTaskManager(self.stop_event, log=log) as task_manager:
            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            ) as session:
                async for context in self.task_generator(log):
                    log.debug("Submitting Task", extra={
                        'task': context.name
                    })
                    task = asyncio.ensure_future(self.request(session, context))
                    task_manager.add(task)

                # TODO: Incorporate some type of timeout as an edge cases if None of the
                # futures are finishing.
                for future in asyncio.as_completed(task_manager.tasks, timeout=None):
                    earliest_future = await future
                    if earliest_future:
                        await task_manager.stop()
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
        self.log_get_request(context, log)

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
            log.error(e, extra=self._log_context(context))
            return None
        else:
            token = self._handle_client_response(
                response, log, extra=self._log_context(context))
            if token:
                self.queues.proxies.good.put_nowait(context.proxy)
            return token

    @auto_logger("Getting Token")
    async def __call__(self, log):
        """
        TODO: We are going to want to start putting proxies back in the queue
        if they resulted in successful requests.
        """
        async with AsyncTaskManager(self.stop_event, log=log) as task_manager:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.THREAD_LIMIT) as executor:
                session = requests.Session()

                async for context in self.task_generator(log):
                    log.debug("Submitting Task", extra={
                        'task': context.name
                    })
                    token_future = executor.submit(self.request, session, context)
                    setattr(token_future, '__context__', context)
                    task_manager.add(token_future)

                for future in concurrent.futures.as_completed(task_manager.tasks):
                    log.debug("Finished Task", extra={
                        'task': future.__context__.name,
                        'proxy': future.__context__.proxy,
                    })
                    result = future.result()
                    if result is not None:
                        await task_manager.stop()
                        executor.shutdown()
                        return result
