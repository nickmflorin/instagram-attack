from __future__ import absolute_import

import asyncio
import aiohttp

from instattack.lib import get_token_from_response, first_successful_completion

from instattack import settings
from instattack.exceptions import TokenNotFound, TokenNotInResponse
from instattack.models import TokenContext

from .base import RequestHandler
from .utils import starting


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

        # Just for now, to make sure we are always using different proxies and
        # nothing with queue is being weird.
        self.proxies_tried = []
        self.attempts = 0

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise TokenNotInResponse()
        return token

    @starting
    async def run(self, loop):
        await self.start_event.wait()
        try:
            token = await asyncio.wait_for(self.fetch(loop),
                timeout=self._token_max_fetch_time)
        except (asyncio.TimeoutError, TimeoutError):
            raise TokenNotFound()
        else:
            return token

    async def fetch(self, loop):
        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
            return await first_successful_completion(
                self.fetch_with_proxy, (loop, session), 3, 20)

    def maintain_proxy(self, proxy):
        """
        >>> Not sure if using these callbacks versus just creating the tasks immediately
        >>> in the async func makes a huge difference, but we'll keep for now.
        """
        self.log.info('Putting Proxy Back in Pool', extra={'proxy': proxy})
        asyncio.create_task(self.proxy_handler.pool.put(proxy))

    def add_proxy_error(self, proxy, e):
        """
        Since errors are stored as foreign keys and not on the proxy, we
        have to save them.  That is a lot of database transactions that
        slow down the process of finding the token.

        We also don't have to worry about those proxies being reused when
        finding the token, since the token is found relatively quickly.

        >>> Not sure if using these callbacks versus just creating the tasks immediately
        >>> in the async func makes a huge difference, but we'll keep for now.
        """
        self.log.info('Saving Proxy Error', extra={'proxy': proxy, 'other': str(e)})
        asyncio.create_task(proxy.add_error(e))

    async def fetch_with_proxy(self, loop, session):
        """
        TODO
        ----
        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        proxy = await self.proxy_handler.pool.get()
        if proxy.unique_id in self.proxies_tried:
            self.log.error('Proxy already tried.', extra={'proxy': proxy})
            return

        self.proxies_tried.append(proxy.unique_id)

        context = TokenContext(index=self.attempts, proxy=proxy)
        self.attempts += 1

        self.log.debug('Attempting Token Fetch', extra={'context': context})
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
                    # Start storing number of successful/unsuccessful requests.
                    self.log.error(e, extra={'context': context})
                    proxy.update_requests()
                    return
                else:
                    # Start storing number of successful/unsuccessful requests.
                    proxy.update_requests()
                    loop.call_soon(self.maintain_proxy, proxy)
                    return token

        # Start storing number of successful/unsuccessful requests.
        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            self.log.error(e, extra={'context': context})
            loop.call_soon(self.add_proxy_error, proxy, e)
            loop.call_soon(self.maintain_proxy, proxy)
            return

        except aiohttp.ClientError as e:
            self.log.error(e, extra={'context': context})
            loop.call_soon(self.add_proxy_error, proxy, e)
            loop.call_soon(self.maintain_proxy, proxy)
            return

        except asyncio.CancelledError:
            return

        except (TimeoutError, asyncio.TimeoutError) as e:
            self.log.error(e, extra={'context': context})
            loop.call_soon(self.add_proxy_error, proxy, e)
            loop.call_soon(self.maintain_proxy, proxy)
            return
