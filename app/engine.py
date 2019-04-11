from __future__ import absolute_import

import logging
import logging.config

import asyncio
import time

from app.lib import exceptions
from app.lib.utils import AysncExceptionHandler, AsyncTaskManager, auto_logger

from .attack import Attacker
from .managers import QueueManager


__all__ = ('Engine', )


log = logging.getLogger(__file__).setLevel(logging.INFO)


class Engine(object):

    def __init__(self, config, global_stop_event, proxies):

        self.config = config
        self.global_stop_event = global_stop_event
        self.queues = QueueManager(proxies={'generated': proxies})

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

    @auto_logger('Running')
    async def run(self, loop, log):

        attacker = Attacker(self.config, self.global_stop_event, self.queues)

        await self.populate_passwords()

        tasks = [
            asyncio.create_task(self.pass_on_proxies()),
            asyncio.create_task(attacker.attack(loop)),
        ]

        async with AsyncTaskManager(self.global_stop_event, log=log, tasks=tasks) as task_manager:
            async with AysncExceptionHandler(log=log):
                await asyncio.gather(*tasks, loop=loop)
                task_manager.stop()
