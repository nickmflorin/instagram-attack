from __future__ import absolute_import

import asyncio
import aiohttp

from instattack.lib import get_token_from_response

from instattack import settings
from instattack.exceptions import TokenNotFound, TokenException, TokenNotInResponse
from instattack.models import TokenContext

from .base import RequestHandler


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
        connection_keepalive_timeout=None,
        **kwargs,
    ):
        super(TokenHandler, self).__init__(
            session_timeout=session_timeout,
            connection_limit=connection_limit,
            connection_force_close=connection_force_close,
            connection_limit_per_host=connection_limit_per_host,
            connection_keepalive_timeout=connection_keepalive_timeout,
            **kwargs,
        )
        self.proxy_handler = proxy_handler
        self._token_max_fetch_time = token_max_fetch_time

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise TokenNotInResponse()
        return token

    async def run(self, loop):
        """
        TODO:
        -----
        Might want to change this method to get_token and the fetch method to
        consume, since the fetch method is really what is consuming the
        proxies.
        """
        await self.start_event.wait()

        async with self.starting(loop):
            try:
                token = await asyncio.wait_for(self.fetch(loop),
                    timeout=self._token_max_fetch_time)
            except asyncio.TimeoutError:
                raise TokenNotFound()
            else:
                return token

    async def fetch(self, loop):
        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
                self.log.debug('Waiting on Fetch')
                token = await self.fetch_until_found(loop, session)
                self.log.debug('Received Result from Token Request')
                if not token:
                    raise TokenException("Token should be non-null here.")
                return token

    async def fetch_until_found(self, loop, session):
        """
        TODO
        ----

        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        async def try_with_proxy(attempt=0):
            self.log.debug('Waiting on Proxy from Pool')

            # Might want to also catch PoolNoProxyError
            # Not sure why proxy_handler.get() does not seem to be working?
            # Well neither are working really.
            proxy = await self.proxy_handler.pool.get()

            self.log.debug('Got Proxy from Pool', extra={'proxy': proxy})
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
                        self.log.error(e, extra={'context': context})

                        # We should maybe start storing num_successful_requests?
                        proxy.update_requests()

                        return await try_with_proxy(attempt=attempt + 1)
                    else:
                        # We should maybe start storing num_successful_requests?
                        # Add confirmed field here.
                        proxy.update_requests()

                        # Try to add to the loop with call_soon so that we can
                        # immediately try again without waiting for the pool.
                        # >>> loop.call_soon_threadsafe(self.proxy_handler.pool.put, proxy)
                        await self.proxy_handler.pool.put(proxy)
                        return token

            # Start storing number of successful requests.
            except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
                # We should maybe start storing num_successful_requests?
                self.log.error(e, extra={'context': context})

                # Since adding error requires saving the proxy, at least right
                # now, maybe we should spit this off in a call_soon method as well.
                await proxy.add_error(e)

                # Try to add to the loop with call_soon so that we can
                # immediately try again without waiting for the pool.
                # >>> loop.call_soon_threadsafe(self.proxy_handler.pool.put, proxy)
                await self.proxy_handler.pool.put(proxy)
                return await try_with_proxy(attempt=attempt + 1)

            except aiohttp.ClientError as e:
                self.log.error(e, extra={'context': context})

                # Since adding error requires saving the proxy, at least right
                # now, maybe we should spit this off in a call_soon method as well.
                await proxy.add_error(e)

                # Try to add to the loop with call_soon so that we can
                # immediately try again without waiting for the pool.
                # >>> loop.call_soon_threadsafe(self.proxy_handler.pool.put, proxy)
                await self.proxy_handler.pool.put(proxy)
                return await try_with_proxy(attempt=attempt + 1)

            except asyncio.CancelledError:
                return

            except (TimeoutError, asyncio.TimeoutError) as e:
                self.log.error(e, extra={'context': context})

                # Since adding error requires saving the proxy, at least right
                # now, maybe we should spit this off in a call_soon method as well.
                await proxy.add_error(e)

                # Try to add to the loop with call_soon so that we can
                # immediately try again without waiting for the pool.
                # >>> loop.call_soon_threadsafe(self.proxy_handler.pool.put, proxy)
                await self.proxy_handler.pool.put(proxy)
                return await try_with_proxy(attempt=attempt + 1)

        # We might have to check if stop_event is set here.
        return await try_with_proxy()
