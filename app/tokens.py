from __future__ import absolute_import

import aiohttp
import asyncio

import logbook

from app import settings
from app.lib import exceptions
from app.lib.logging import token_task_log
from app.lib.models import TokenContext
from app.lib.utils import get_token_from_response, cancel_remaining_tasks

from .requests import request_handler


log = logbook.Logger(__file__)


class token_handler(request_handler):

    __handlername__ = 'token'

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
        return token

    @token_task_log
    async def request(self, session, context, retry=1):
        log = logbook.Logger('Token Fetch')

        # self.log_get_request(context, log, retry=retry)

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
                    log.notice('Got Token', extra={'context': context})
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
            log.error('TimeoutError', extra={'context': context})
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

                log.info("Fetching Token", extra={'context': context})
                task = asyncio.ensure_future(self.request(session, context))
                tasks.append(task)

            # TODO: Incorporate some type of timeout as an edge cases if None of the
            # futures are finishing.
            for future in asyncio.as_completed(tasks, timeout=None):
                earliest_future = await future
                if earliest_future:
                    await cancel_remaining_tasks(tasks)
                    return earliest_future
