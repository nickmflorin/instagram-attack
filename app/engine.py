from __future__ import absolute_import

import signal

import asyncio

from app.lib import exceptions
from app.logging import AppLogger
from app.lib.utils import cancel_remaining_tasks, handle_global_exception

from .handlers import (
    password_handler, token_handler, proxy_handler, results_handler)


__all__ = ('Engine', )


# May want to catch other signals too - these are not currently being
# used, but could probably be expanded upon.
SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)


log = AppLogger('Engine')


class Engine(object):

    def __init__(self, config, get_proxy_handler, post_proxy_handler, attempts,
            results):

        self.config = config

        self.attempts = attempts
        self.results = results

        self.results_handler = results_handler(config, results, attempts)
        # self.token_handler = token_handler(get_proxy_handler, config, results, attempts)
        self.password_handler = password_handler(post_proxy_handler, config, results, attempts)

        self.consumers = ()

    async def cancel_consumers(self):
        if len(self.consumers) != 0:
            log.warning(f'Shutting Down {len(self.consumers)} Consumers...')
            for consumer in self.consumers:
                consumer.cancel()
            log.notice('Done')

    async def shutdown(self, loop, signal=None):
        log.warning("Shutting Down...")

        # We have to do this for now for when we find a successful login,
        # otherwise we hit an error in run.py about the loop being closed
        # before all futures finished - being caused by the proxy_broker.
        if signal:
            log.info(f'Received exit signal {signal.name}...')

        # Probably need try excepts for these just in case they were already
        # stoped.
        # log.warning('Shutting Down Proxy Servers...')
        # # self.get_server.stop()
        # # self.post_server.stop()
        # log.notice('Done')

        await self.results_handler.dump()
        await self.cancel_consumers()

        log.warning('Cancelling Remaining Tasks...')
        await cancel_remaining_tasks()
        log.notice('Done')

        loop.stop()
        log.notice('Shutdown Complete')

    def attach_signals(self, loop):
        for s in SIGNALS:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(
                    self.shutdown(loop, signal=s)
                )
            )

    async def set_token(self, loop, get_proxy_handler, stop_event):

        self.attach_signals(loop)

        token = None
        while not stop_event.is_set():
            token = await self.token_handler.consume(loop)
            if token is None:
                raise exceptions.FatalException(
                    "The allowable attempts to retrieve a token did not result in a "
                    "valid response containing a token.  This is most likely do to "
                    "a connection error."
                )

            log.notice(f"Setting Token {token}")
            stop_event.set()
        # get_proxy_handler.cancel()
        return token

    async def run(self, loop):

        self.attach_signals(loop)

        log.notice('Starting Proxy Handler')
        # proxy_task = asyncio.create_task(self.get_proxy_handler.consume(loop))

        # self.consumers = (
        #     asyncio.create_task(self.get_proxy_handler.consume(loop)),
        # )

        token = await self.token_handler.consume(loop)
        if token is None:
            raise exceptions.FatalException(
                "The allowable attempts to retrieve a token did not result in a "
                "valid response containing a token.  This is most likely do to "
                "a connection error."
            )

        log.notice(f"Setting Token {token}")
        self.get_server.stop()

        log.notice('Starting Results Handler')
        log.notice('Starting Password Handler')
        self.consumers += (
            asyncio.ensure_future(self.post_proxy_handler.consume(loop)),
            asyncio.ensure_future(self.results_handler.consume(loop)),
            asyncio.ensure_future(self.password_handler.consume(loop)),
        )

        try:
            # Wait until the password consumer has processed all the passwords.
            log.debug('Awaiting Password Consumer')
            await self.consumers[3]
        except Exception as e:
            log.critical("Uncaught Exception")
            log.exception(e)
            return await self.shutdown(loop)
        except KeyboardInterrupt:
            log.critical('Keyboard Interrupt')
            return await self.shutdown(loop)
        else:
            log.notice('Passwords Consumed')
            return await self.shutdown(loop)
