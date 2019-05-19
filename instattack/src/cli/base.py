from argparse import ArgumentTypeError
import asyncio
from platform import python_version
from plumbum import cli
import tortoise

from instattack import logger
from instattack.conf import Configuration
from instattack.src.users import User

from .attack import post_handlers, attack


class BaseApplication(cli.Application):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.
    """
    log = logger.get_sync('Application')
    _config = None

    @property
    def config(self):
        if not self._config:
            self._config = Configuration.load()
            # TODO: Validate just the structure of the configuration object
            # here, but not the path.
        return self._config

    async def get_user(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            self.log.error(f'User {username} does not exist.')
            return None
        else:
            user.setup()
            return user

    async def check_if_user_exists(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            return None
        else:
            return user

    def post_handlers(self, user):
        return post_handlers(user, self.config)


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


@EntryPoint.subcommand('attack')
class BaseAttack(BaseApplication):

    __name__ = 'Run Attack'

    def main(self, username):
        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        result = loop.run_until_complete(self.attempt_attack(loop, user))
        if result:
            self.log.info(f'Authenticated User!', extra={
                'password': result.context.password
            })

    async def attempt_attack(self, loop, user):
        return await attack(loop, user, self.config)
