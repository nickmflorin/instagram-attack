from __future__ import absolute_import

import logbook
import time
import sys

import asyncio

from app.lib import exceptions
from app.lib.models import Proxy

from .handlers import login_handler, token_handler


__all__ = ('Engine', )


log = logbook.Logger(__file__)


class proxy_handler(object):

    def __init__(self, config, global_stop_event, generated):
        self.config = config
        self.global_stop_event = global_stop_event

        self.generated = generated
        self.good = asyncio.Queue()
        self.handled = asyncio.Queue()

    async def get_best(self):
        # We could run into race conditions here - we may want to have a try
        # except.
        if not self.good.empty():
            # Don't want to immediately put proxies back in because we will
            # hit too many requests with same proxy, we shoudl eventually
            # start using a proxy list.
            proxy = await self.good.get()
            # self.good.put_nowait(proxy)
            return proxy
        return await self.handled.get()

    async def produce_proxies(self):
        """
        We are going to use this to better control the flow of proxies into the
        system.

        We don't need them to be funneling through at super fast speeds, and we
        also may want to validate them in some way before providing them to the
        consumers.
        """
        log.notice('Starting...')

        while not self.global_stop_event.is_set():
            proxy = await self.generated.get()
            if proxy:
                if self.config.proxysleep:
                    time.sleep(self.config.proxysleep)

                proxy = Proxy(port=proxy.port, host=proxy.host)
                self.handled.put_nowait(proxy)
            else:
                log.critical('No New Proxies')


class Engine(object):

    def __init__(self, config, global_stop_event, proxies):

        self.config = config
        self.global_stop_event = global_stop_event

        self.proxy_handler = proxy_handler(config, global_stop_event, proxies)
        self.login_handler = login_handler(config, global_stop_event, self.proxy_handler)
        self.token_handler = token_handler(config, global_stop_event, self.proxy_handler)

    async def produce_passwords(self, passwords):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        log = logbook.Logger('Producing Passwords')
        log.notice('Starting...')

        count = 0
        for password in self.config.user.get_new_attempts():
            if self.config.limit is not None and count == self.config.limit:
                break
            await passwords.put(password)
            count += 1

    async def consume_results(self, results, attempts):
        log = logbook.Logger('Consuming Results')

        while True:
            # wait for an item from the producer
            result = await results.get()
            if not result or not result.conclusive:
                raise exceptions.FatalException(
                    "Result should be valid and conslusive."
                )

            if result.authorized:
                log.notice(result)
                log.notice(result.context.password)

                # We are going to have to do this a cleaner way with the global
                # stop event.
                sys.exit()
            else:
                log.error(result)

            await attempts.put(result.context.password)

            # Notify the queue that the item has been processed
            results.task_done()

    async def run(self, loop):

        passwords = asyncio.Queue()
        attempts = asyncio.Queue()
        results = asyncio.Queue()

        proxy_producer = asyncio.ensure_future(
            self.proxy_handler.produce_proxies()
        )

        token = await self.token_handler.fetch()
        if token is None:
            raise exceptions.FatalException(
                "The allowable attempts to retrieve a token did not result in a "
                "valid response containing a token.  This is most likely do to "
                "a connection error."
            )

        log.notice("Set Token", extra={'token': token})

        results_consumer = asyncio.ensure_future(
            self.consume_results(results, attempts)
        )

        password_consumer = asyncio.ensure_future(
            self.login_handler.consume_passwords(passwords, results, token)
        )

        # Run the main password producer and wait for completion
        await self.produce_passwords(passwords)
        log.notice('Passwords Produced')
        answer = input("Total of %s passwords, continue?" % passwords.qsize())
        if answer.lower() != 'y':
            sys.exit()

        # Wait until the password consumer has processed all the passwords.
        log.debug('Awaiting Password Consumer')
        await password_consumer
        log.notice('Passwords Consumed')

        # If the consumer is still awaiting for an item, cancel it.
        log.debug('Cancelling Password Consumer')
        password_consumer.cancel()
        log.info('Password Consumer Cancelled')

        log.debug('Cancelling Results Consumer')
        results_consumer.cancel()
        log.info('Results Consumer Cancelled')

        log.debug('Cancelling Proxy Producer')
        proxy_producer.cancel()
        log.info('Proxy Producer Cancelled')

        log.info('Dumping Attempts')
        while not attempts.empty():
            log.info(await attempts.get())
