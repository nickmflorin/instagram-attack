from __future__ import absolute_import

import logging

import aiohttp
import asyncio

from app import settings
from app.lib import exceptions
from app.lib.utils import auto_logger, format_proxy, get_token_from_response

from .requests import request_handler
from .managers import TaskManager, TokenTaskContext


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


class token_handler(request_handler):

    __handlername__ = 'token'

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

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
                timeout=self.FETCH_TIME,
                proxy=format_proxy(context.proxy)
            ) as response:
                # Raise for status is automatically performed, so we do not have
                # to have a client response handler.
                try:
                    token = self._get_token_from_response(response)
                except exceptions.TokenNotInResponse as e:
                    log.warning(e, extra=self._log_context(context, response=response))
                    return None
                else:
                    log.success('Got Token', extra={'task': context.name})
                    await self.queues.proxies.good.put(context.proxy)
                    return token

        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            log.warning(e, extra=self._log_context(context))

            # We probably want to lower this number
            if retry < self.MAX_REQUEST_RETRY_LIMIT:
                # Session should still be alive.
                await asyncio.sleep(1)
                retry += 1
                return await self.request(session, context, retry=retry)
            else:
                log.error(e, extra=self._log_context(context))
                return None

        except aiohttp.ClientError as e:
            log.error(e, extra=self._log_context(context))
            return None

        except asyncio.CancelledError:
            return None

        except Exception as e:
            raise exceptions.FatalException(
                f'Uncaught Exception: {str(e)}', extra=self._log_context(context))

    @auto_logger("Fetching Token")
    async def fetch(self, log):
        """
        Asyncio Docs:

        asyncio.as_completed

            Run awaitable objects in the aws set concurrently. Return an iterator
            of Future objects. Each Future object returned represents the earliest
            result from the set of the remaining awaitables.

            Raises asyncio.TimeoutError if the timeout occurs before all Futures are done.
        """
        manager = TaskManager(self.stop_event, log=log, tasks=[], limit=self.FIRST_ATTEMPT_LIMIT)
        while manager.active:
            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            ) as session:

                proxy = await self.queues.proxies.get_best()
                context = TokenTaskContext(index=manager.index, proxy=proxy)
                task = asyncio.ensure_future(self.request(session, context))
                manager.submit(task, context)

                # TODO: Incorporate some type of timeout as an edge cases if None of the
                # futures are finishing.
                for future in asyncio.as_completed(manager.tasks, timeout=None):
                    earliest_future = await future
                    if earliest_future:
                        await manager.stop()
                        return earliest_future
