from __future__ import absolute_import

import asyncio
import aiohttp

from instattack import settings
from instattack.lib import starting
from instattack.exceptions import TokenNotFound, TokenNotInResponse

from instattack.core.models import TokenContext
from instattack.core.utils import limit_on_success

from .base import GetRequestHandler


class TokenHandler(GetRequestHandler):

    __name__ = 'Token Handler'

    def __init__(self, proxy_handler, token_max_fetch_time=None, **kwargs):
        kwargs.setdefault('method', 'GET')
        super(TokenHandler, self).__init__(proxy_handler, **kwargs)

        self._token_max_fetch_time = token_max_fetch_time

        # Just for now, to make sure we are always using different proxies and
        # nothing with queue is being weird.
        self.proxies_tried = []
        self.attempts_index = 0

    @starting
    async def run(self, loop):
        """
        ClientSession
        -------------
        When ClientSession closes at the end of an async with block (or through
        a direct ClientSession.close() call), the underlying connection remains
        open due to asyncio internal details. In practice, the underlying
        connection will close after a short while. However, if the event loop is
        stopped before the underlying connection is closed, an ResourceWarning:
        unclosed transport warning is emitted (when warnings are enabled).

        To avoid this situation, a small delay must be added before closing the
        event loop to allow any open underlying connections to close.
        <https://docs.aiohttp.org/en/stable/client_advanced.html>
        """
        # Wait for start event to signal that we are ready to start making
        # requests with the proxies.
        await self.start_event.wait()
        try:
            token = await asyncio.wait_for(self.fetch(loop),
                timeout=self._token_max_fetch_time)
        except (asyncio.TimeoutError, TimeoutError):
            raise TokenNotFound()
        else:
            await asyncio.sleep(0)
            return token

    async def token_task_generator(self, loop, session):
        while True:
            proxy = await self.proxy_handler.pool.get()

            if proxy.unique_id not in self.proxies_tried:
                context = TokenContext(index=self.attempts_index, proxy=proxy)
                yield self.fetch_with_proxy(loop, session, context, proxy)

                self.proxies_tried.append(proxy.unique_id)
                self.attempts_index += 1

            else:
                self.log.error('Proxy already tried.', extra={'proxy': proxy})

    async def fetch(self, loop, batch_size=3, max_tries=20):
        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
            return await limit_on_success(
                self.token_task_generator(loop, session),
                batch_size=batch_size,
                max_tries=max_tries
            )

    async def fetch_with_proxy(self, loop, session, context, proxy):
        """
        TODO
        ----
        We might want to incorporate handling of a "Too Many Requests" exception
        that is smarter and will notify the handler to use a different proxy and
        note the time.
        """
        try:
            async with session.get(
                settings.INSTAGRAM_URL,
                raise_for_status=True,
                headers=self._headers(),
                proxy=proxy.url,  # Only HTTP Proxies Are Supported by AioHTTP?
            ) as response:
                try:
                    token = self._get_token_from_response(response)
                except TokenNotInResponse as e:
                    # This seems to happen a lot more when using the HTTP scheme
                    # vs. the HTTPS scheme.
                    # Start storing number of successful/unsuccessful requests.
                    loop.call_soon(self.maintain_proxy, proxy)
                    self.log.error(e, extra={'context': context, 'response': response})
                else:
                    # Start storing number of successful/unsuccessful requests.
                    # Note that proxy was a good candidate.
                    loop.call_soon(self.maintain_proxy, proxy)
                    return token

        # Start storing number of successful/unsuccessful requests.
        except (aiohttp.ClientProxyConnectionError, aiohttp.ServerTimeoutError) as e:
            self.log.error(e, extra={'context': context})
            loop.call_soon(self.add_proxy_error, proxy, e)

        except aiohttp.ClientError as e:
            self.log.error(e, extra={'context': context})
            loop.call_soon(self.add_proxy_error, proxy, e)

        except asyncio.CancelledError:
            loop.call_soon(self.maintain_proxy, proxy)

        except (TimeoutError, asyncio.TimeoutError) as e:
            self.log.error(e, extra={'context': context})
            loop.call_soon(self.add_proxy_error, proxy, e)
