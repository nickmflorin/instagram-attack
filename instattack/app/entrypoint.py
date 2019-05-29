from argparse import ArgumentTypeError
import asyncio
from platform import python_version
from plumbum import cli
import tortoise

from instattack.conf import Configuration
from instattack.app.exceptions import ArgumentError

from .users.models import User
from .base import HandlerMixin


class BaseApplication(cli.Application, HandlerMixin):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.
    """

    def config(self):
        return Configuration.load()

    def get_user(self, loop, username):

        async def _get_user(username):
            async with self.async_logger('get_user') as log:
                try:
                    user = await User.get(username=username)
                except tortoise.exceptions.DoesNotExist:
                    await log.error(f'User {username} does not exist.')
                    return None
                else:
                    user.setup()
                    return user

        return loop.run_until_complete(_get_user(username))

    async def check_if_user_exists(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            return None
        else:
            return user


class SelectOperatorApplication(BaseApplication):

    def main(self, *args):
        loop = asyncio.get_event_loop()
        operator = self.get_operator(*args)
        loop.run_until_complete(operator(loop))
        return 1

    def get_operator(self, *args):
        if len(args) == 0:
            if not hasattr(self, 'operation'):
                raise ArgumentError('Missing positional argument.')
            return self.operation
        else:
            method_name = args[0]
            if not hasattr(self, method_name):
                raise ArgumentError('Invalid positional argument.')

            return getattr(self, method_name)


class EntryPoint(BaseApplication):

    def main(self, *args):
        self.validate(*args)

    def validate(self, *args):
        if int(python_version()[0]) < 3:
            raise EnvironmentError('Please use Python 3')

        if args:
            raise ArgumentTypeError("Unknown command %r" % (args[0]))

        # The nested command will be`None if no sub-command follows
        if not self.nested_command:
            raise ArgumentTypeError("No command given")
