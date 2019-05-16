import asyncio
import aiohttp
import collections

from instattack import settings
from instattack.exceptions import ClientResponseError
from instattack.lib import starting_context

from instattack.core.utils import limit_on_success

from .exceptions import TokenNotFound
from .models import TokenContext
from .base import GetRequestHandler


class TokenHandler(GetRequestHandler):

    __name__ = 'Token Handler'

    def __init__(self, config, proxy_handler, **kwargs):
        super(TokenHandler, self).__init__(config, proxy_handler, **kwargs)

        self.timeout = config['token']['timeout']
        self.batch_size = config['token']['batch_size']
        self.max_tries = config['token']['max_tries']

        self.proxies_count = collections.Counter()  # Indexed by Proxy Unique ID
        self.num_attempts = 0
        self._all_tasks = []

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

        self.log.start('Starting Session...')
        async with aiohttp.ClientSession(
            connector=self._connector,
            timeout=self._timeout
        ) as session:
            result = await limit_on_success(
                self.token_task_generator(loop, session),
                batch_size=self.batch_size,
                max_tries=self.max_tries
            )

        self.log.complete('Closing Session')
        await asyncio.sleep(0)

        # If we return the result right away, the handler will be stopped and
        # leftover tasks will be cancelled.  We have to make sure to save the
        # proxies before doing that.
        leftover = [tsk for tsk in self._all_tasks if not tsk.done()]
        await asyncio.gather(*leftover)
        return result

    async def fetch_with_proxy(self, loop, session, context, proxy):
        self.log.debug('Submitting Request', extra={'context': context})
        try:
            async with session.get(
                settings.INSTAGRAM_URL,
                raise_for_status=True,
                headers=settings.HEADERS(),
                proxy=proxy.url,  # Only HTTP Proxies Are Supported by AioHTTP?
            ) as response:
                try:
                    token = await self.handle_client_response(response)
                except ClientResponseError as e:
                    # This seems to happen a lot more when using the HTTP scheme
                    # vs. the HTTPS scheme.  Not sure if we want to note this as
                    # an error or inconclusive.
                    self.log.error(e, extra={
                        'context': context,
                        'response': response
                    })
                    task = asyncio.create_task(self.proxy_error(proxy, e))
                    self._all_tasks.append(task)
                else:
                    task = asyncio.create_task(self.proxy_success(proxy))
                    self._all_tasks.append(task)
                    return token

        except Exception as e:
            task = await self.handle_request_error(e, proxy, context)
            if task:
                self._all_tasks.append(task)
