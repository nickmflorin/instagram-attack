import asyncio
import aiohttp
import collections

from instattack import settings
from instattack.lib import starting_context

from instattack.core.utils import limit_on_success
from instattack.core.base import RequestHandler

from .exceptions import TokenNotFound, TokenNotInResponse
from .models import TokenContext
from .utils import get_token_from_response


class GetRequestHandler(RequestHandler):

    __method__ = 'GET'

    def _get_token_from_response(self, response):
        token = get_token_from_response(response)
        if not token:
            raise TokenNotInResponse()
        return token


class TokenHandler(GetRequestHandler):

    __name__ = 'Token Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(TokenHandler, self).__init__(config, proxy_handler, **kwargs)

        self.timeout = config['token']['timeout']
        self.batch_size = config['token']['batch_size']
        self.max_tries = config['token']['max_tries']

        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID
        self.num_attempts = 0

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

        self.log.once('Waiting on Start Event')
        await self.start_event.wait()

        with starting_context(self):
            try:
                token = await asyncio.wait_for(self.fetch(loop), timeout=self.timeout)
            except (asyncio.TimeoutError, TimeoutError):
                raise TokenNotFound()
            else:
                await asyncio.sleep(0)
                return token

    async def token_task_generator(self, loop, session):
        while True:
            self.log.once('Waiting on Proxy from Pool')
            proxy = await self.proxy_handler.pool.get()
            if proxy:
                if proxy.unique_id in self.proxies_count:
                    self.log.warning(
                        f'Already Used Proxy {self.proxies_count[proxy.unique_id]} Times.',
                        extra={'proxy': proxy}
                    )

                self.proxies_count[proxy.unique_id] += 1

                context = TokenContext(index=self.num_attempts, proxy=proxy)
                yield self.fetch_with_proxy(loop, session, context, proxy)

                self.num_attempts += 1

            else:
                self.log.error('Proxy already tried.', extra={'proxy': proxy})

    async def fetch(self, loop):
        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
            return await limit_on_success(
                self.token_task_generator(loop, session),
                batch_size=self.batch_size,
                max_tries=self.max_tries
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
                    loop.call_soon(self.add_proxy_error, proxy, e)
                    self.log.error(e, extra={
                        'context': context,
                        'response': response
                    })
                else:
                    # Start storing number of successful/unsuccessful requests.
                    # Note that proxy was a good candidate.
                    loop.call_soon(self.add_proxy_success, proxy)
                    return token

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
