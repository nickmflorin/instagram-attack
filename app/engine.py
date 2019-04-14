from __future__ import absolute_import

import time
import signal
import sys

import asyncio

from app.lib import exceptions
from app.lib.logging import AppLogger
from app.lib.models import Proxy

from .handlers import login_handler, token_handler


__all__ = ('Engine', )


log = AppLogger('Engine')


class proxy_handler(object):

    def __init__(self, config, generated):
        self.config = config

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

        while True:
            proxy = await self.generated.get()
            if proxy:
                if self.config.proxysleep:
                    time.sleep(self.config.proxysleep)

                proxy = Proxy(port=proxy.port, host=proxy.host)
                self.handled.put_nowait(proxy)
            else:
                log.critical('No New Proxies')


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

    async def produce_passwords(self, passwords):
        """
        Retrieves passwords generated passwords that have not been attempted
        from the User object and populates the password queue.
        """
        log = AppLogger('Producing Passwords')
        log.notice('Starting...')

        count = 0
        for password in self.config.user.get_new_attempts():
            if self.config.limit is not None and count == self.config.limit:
                break
            await passwords.put(password)
            count += 1

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
            if self.total is not None:
                log.notice("{0:.2%}".format(float(index) / self.total))

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

    async def run(self, loop, passwords, attempts, results):

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
            self.login_handler.consume_passwords(passwords, results, token)
        )

        self.consumers = [password_consumer, results_consumer, proxy_producer]

        # Run the main password producer and wait for completion
        await self.produce_passwords(passwords)
        log.notice('Passwords Produced')
        answer = input("Total of %s passwords, continue?" % passwords.qsize())
        if answer.lower() != 'y':
            sys.exit()

        self.total = passwords.qsize()

        # Wait until the password consumer has processed all the passwords.
        log.debug('Awaiting Password Consumer')

        # Not sure why we need this here and in the run.py file but we'll let it be for now.
        def signal_handler(sig, frame):
            self.shutdown(loop, attempts, forced=False)
        signal.signal(signal.SIGINT, signal_handler)

        # TODO: Maybe try to add signals here for keyboard interrupt as well.
        # await password_consumer
        try:
            await password_consumer
        except Exception as e:
            log.critical("Uncaught Exception")
            import ipdb; ipdb.set_trace()
            log.critical(e)
            # Having trouble calling this outside of run.py without having issues
            # closing the loop with ongoing tasks.  So we force.
            return await self.shutdown(loop, attempts, forced=True)
        except KeyboardInterrupt:
            log.critical('Keyboard Interrupt')
            return await self.shutdown(loop, attempts, forced=True)
        else:
            log.notice('Passwords Consumed')
            return await self.slowdown()
