import asyncio
from plumbum import cli

from instattack import logger
from instattack.src.proxies.cli import BaseProxy

from .base import EntryPoint, BaseApplication


@EntryPoint.subcommand('test')
class TestEntryPoint(BaseApplication):
    pass


@TestEntryPoint.subcommand('proxies')
class TestProxies(BaseProxy):
    """
    Will be used to test proxies against simple request URLs.
    Not sure if we will maintain this.
    """
    __name__ = 'Test Proxies'


@TestEntryPoint.subcommand('token')
class TestToken(BaseApplication):

    __name__ = 'Test Get Token'

    def main(self):
        loop = asyncio.get_event_loop()

        # Token will be None if an exception occured.
        token = self.get_token(loop)
        if not token:
            return


@TestEntryPoint.subcommand('login')
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

        # Why is it that test_login() is always a running task even after
        # it returns?
        result = loop.run_until_complete(self.test_login(loop, user, password))
        log.complete(str(result))

    async def test_login(self, loop, user, password):
        log = logger.get_async(__name__, subname='test_login')

        proxy_handler, password_handler = self.post_handlers(user)

        results = await asyncio.gather(
            password_handler.attempt_single_login(loop, password),
            proxy_handler.run(loop),
        )

        # We might not need to stop proxy handler.
        await log.debug('Stopping Proxy Handler...')
        await proxy_handler.stop(loop)

        await log.debug('Returning Result')
        return results[0]
