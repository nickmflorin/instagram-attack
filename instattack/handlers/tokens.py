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

    arguments = (
        ('fetch_time', ),
        ('connection_limit', ),
        ('connector_timeout', ),
        ('token_max_wait_time', ),
    )

    def __init__(self, proxy_handler, **kwargs):
        self.proxy_handler = proxy_handler
        super(TokenHandler, self).__init__(method=self.__method__, **kwargs)

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
                        await self.proxy_handler.put(proxy)
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
            connector=self.connector,
            timeout=self.timeout
        ) as session:
            with self.log.start_and_done('Finding Token'):
                task = asyncio.ensure_future(self.fetch(session))

                with stopit.SignalTimeout(self.token_max_wait_time) as timeout_mgr:
                    token = await task
                    if not token:
                        raise exceptions.FatalException("Token should be non-null here.")

                if timeout_mgr.state == timeout_mgr.TIMED_OUT:
                    raise exceptions.InternalTimeout("Timed out waiting for token.")

                # See related notes in ProxyPool and ProxyHandler about potential
                # duplicate meaning of putting None in the proxy pool.
                await self.proxy_handler.pool.put(None)

                return token
