from __future__ import absolute_import

import logging
import logging.config

import asyncio

from app.lib import exceptions
from app.lib.utils import auto_logger
from app.requests import FuturesLogin
from app.handlers import AysncExceptionHandler


__all__ = ('EngineAsync', )


log = logging.getLogger(__file__).setLevel(logging.INFO)


class ProxyManager(object):

    def __init__(self, generated=None, good=None, handled=None):
        self.generated = generated or asyncio.Queue()
        self.good = good or asyncio.Queue()
        self.handled = handled or asyncio.Queue()

    async def get_best(self):
        # We could run into race conditions here - we may want to have a try
        # except.
        if not self.good.empty():
            return await self.good.get()
        return await self.handled.get()


class PasswordManager(object):

    def __init__(self, generated=None, attempted=None):
        self.generated = generated or asyncio.Queue()
        self.attempted = attempted or asyncio.Queue()


class QueueManager(object):

    def __init__(self, **kwargs):
        self.proxies = ProxyManager(**kwargs.get('proxies', {}))
        self.passwords = PasswordManager(**kwargs.get('passwords', {}))


class Configuration(object):

    def __init__(self, mode, test=False):
        self.mode = mode
        self.test = test

    @property
    def a_sync(self):
        return self.mode == 'async'

    @property
    def sync(self):
        return self.mode == 'sync'


class EngineAsync(object):

    def __init__(self, user, global_stop_event, proxies, mode='async', test=False):
        self.user = user
        self.global_stop_event = global_stop_event

        self.config = Configuration(mode, test=test)
        self.queues = QueueManager(proxies={'generated': proxies})

        if self.config.test and not self.user.password:
            raise exceptions.FatalException(
                "Must provide password to test attack."
            )

    @auto_logger("Populating Passwords")
    async def populate_passwords(self, log):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        for password in self.user.get_new_attempts():
            self.queues.passwords.generated.put_nowait(password)

        if self.queues.passwords.generated.empty():
            raise exceptions.FatalException("No new passwords to try.")

        log.info(f"Populated {self.queues.passwords.generated.qsize()} Passwords")

    @auto_logger('Attacking')
    async def login(self, loop, log, mode='async'):

        login_handler = FuturesLogin(
            self.user,
            self.global_stop_event,
            self.queues,
            self.config,
        )

        async with AysncExceptionHandler(log=log):
            return await login_handler.login(loop)

    @auto_logger('Proxy Handler')
    async def pass_on_proxies(self, log):
        """
        We are going to use this to better control the flow of proxies into the
        system.

        We don't need them to be funneling through at super fast speeds, and we
        also may want to validate them in some way before providing them to the
        consumers.
        """
        while not self.global_stop_event.is_set():
            proxy = await self.queues.proxies.generated.get()
            if proxy:
                log.debug('Got Proxy', extra={'proxy': proxy})
                self.queues.proxies.handled.put_nowait(proxy)
            else:
                log.debug('No New Proxies')

    @auto_logger('Attacking')
    async def run(self, loop, log):
        await self.populate_passwords()

        tasks = [
            asyncio.create_task(self.pass_on_proxies()),
            asyncio.create_task(self.login(loop, mode='futures')),
        ]

        async with AysncExceptionHandler(log=log):
            await asyncio.gather(*tasks, loop=loop)
