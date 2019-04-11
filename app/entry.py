from __future__ import absolute_import

from app.lib import exceptions
from app.lib.utils import (
    AysncExceptionHandler, SyncExceptionHandler, auto_logger)

from .login import async_login_handler, futures_login_handler
from .tokens import async_token_handler, futures_token_handler


"""
TODO:

We might want to use AysncExceptionHandler, SyncExceptionHandler in the
entrypoint classes.
"""


class EntryPoint(object):

    def __init__(self, config, global_stop_event, queues):
        self.global_stop_event = global_stop_event
        self.queues = queues
        self.config = config

    @auto_logger("Login")
    async def login(self, loop, log):
        token = await self.token_handler()
        if token is None:
            raise exceptions.FatalException(
                "The allowable attempts to retrieve a token did not result in a "
                "valid response containing a token.  This is most likely do to "
                "a connection error."
            )

        log.success("Set Token", extra={'token': token})

        # Check if --test was provided, and if so only use one password that is
        # attached to user object.
        # There is no synchronous version of the async login, only the futures
        # login.
        if self.config.futures:
            if self.config.sync:
                with SyncExceptionHandler():
                    result = self.login_handler.run_synchronous(
                        token, self.config.user.password)
            else:
                async with AysncExceptionHandler():
                    result = await self.login_handler.run_asynchronous(
                        token, self.config.user.password)
        else:
            if self.config.sync:
                async with AysncExceptionHandler():
                    result = await self.login_handler.run_synchronous(
                        token, self.config.user.password)
            else:
                async with AysncExceptionHandler():
                    result = await self.login_handler.run_asynchronous(
                        token, self.config.user.password)

        if result.authorized:
            log.success('Authenticated')
        else:
            log.success('Not Authenticated')
            print(result.__dict__)

        self.global_stop_event.set()


class AsyncEntryPoint(EntryPoint):

    def __init__(self, config, global_stop_event, queues):
        super(AsyncEntryPoint, self).__init__(config, global_stop_event, queues)
        self.login_handler = async_login_handler(config.user, global_stop_event, queues)
        self.token_handler = async_token_handler(global_stop_event, queues)


class FuturesEntryPoint(EntryPoint):

    def __init__(self, config, global_stop_event, queues):
        super(FuturesEntryPoint, self).__init__(config, global_stop_event, queues)
        self.login_handler = futures_login_handler(config.user, global_stop_event, queues)
        self.token_handler = futures_token_handler(global_stop_event, queues)
