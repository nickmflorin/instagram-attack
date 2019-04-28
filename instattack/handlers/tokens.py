from __future__ import absolute_import

import asyncio
import aiohttp

import stopit

from instattack import exceptions
from instattack.conf import settings

from .utils import get_token_from_response
from .models import TokenContext

from .base import RequestHandler


class TokenHandler(RequestHandler):

    __method__ = 'GET'

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
        self.proxy_handler = proxy_handler
        self._token_max_fetch_time = token_max_fetch_time

        super(TokenHandler, self).__init__(
            'Token Handler',
            method=self.__method__,
            session_timeout=session_timeout,
            connection_limit=connection_limit,
            connection_force_close=connection_force_close,
            connection_limit_per_host=connection_limit_per_host,
            connection_keepalive_timeout=connection_keepalive_timeout
        )

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise exceptions.TokenNotInResponse()
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
                    except exceptions.TokenNotInResponse as e:
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
        async with aiohttp.ClientSession(
            connector=self._connector,
            # timeout=self._timeout
        ) as session:
            with self.log.start_and_done('Finding Token'):
                task = asyncio.ensure_future(self.fetch(session))

                with stopit.SignalTimeout(2) as timeout_mgr:
                # with stopit.SignalTimeout(self._token_max_fetch_time) as timeout_mgr:
                    token = await task
                    if not token:
                        raise exceptions.FatalException("Token should be non-null here.")

                if timeout_mgr.state == timeout_mgr.TIMED_OUT:
                    raise exceptions.InternalTimeout("Timed out waiting for token.")

                # See related notes in ProxyPool and ProxyHandler about potential
                # duplicate meaning of putting None in the proxy pool.
                await self.proxy_handler.pool.put(None)
                return token
