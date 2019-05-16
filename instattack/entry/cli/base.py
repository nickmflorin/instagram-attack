from argparse import ArgumentTypeError
import asyncio
from platform import python_version
from plumbum import cli
import tortoise
import os

from instattack.lib import validate_log_level
from instattack.users import User
from instattack.mixins import LoggableMixin
from instattack.attack import post_handlers, attack

from instattack.entry.config import Configuration


class BaseApplication(cli.Application, LoggableMixin):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.
    """

    # Even though we are not using the log level internally, and setting
    # it in __main__, we still have to allow this to be a switch otherwise
    # CLI will complain about unknown switch.
    level = cli.SwitchAttr("--level", validate_log_level, default='INFO')
    _config_path = cli.SwitchAttr("--config", str, default="conf.yaml")
    _config = None

    @property
    def config(self):
        if not self._config:
            self._config = Configuration(self._config_path)
            self._config.validate()
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

    def post_handlers(self, user):
        return post_handlers(user, self.config)

    def silent_shutdown(self):
        os.environ['SILENT_SHUTDOWN'] = "1"


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

    async def attempt_attack(self, loop):
        return await attack(loop, self.user, self.config)


@BaseAttack.subcommand('run')
class AttackRun(BaseAttack):

    __name__ = 'Run Attack'

    def main(self, username):
        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        result = loop.run_until_complete(self.attempt_attack(loop))
        if result:
            self.log.info(f'Authenticated User!', extra={
                'password': result.context.password
            })
