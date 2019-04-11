from __future__ import absolute_import

from app.lib import exceptions
from app.lib.utils import AysncExceptionHandler, auto_logger

from .login import login_handler
from .tokens import token_handler


"""
TODO:

We might want to use AysncExceptionHandler, SyncExceptionHandler in the
entrypoint classes.
"""


class Attacker(object):

    def __init__(self, config, global_stop_event, queues):
        self.global_stop_event = global_stop_event
        self.queues = queues
        self.config = config

        self.login_handler = login_handler(config, global_stop_event, queues)
        self.token_handler = token_handler(config, global_stop_event, queues)

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
        async with AysncExceptionHandler():
            result = await self.login_handler.login(token, self.config.user.password)

            if result.authorized:
                log.success('Authenticated')
            else:
                log.success('Not Authenticated')
                print(result.__dict__)

            self.global_stop_event.set()
