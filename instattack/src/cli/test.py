import aiojobs
import asyncio
from plumbum import cli

from instattack import logger
from instattack.src.proxies.cli import BaseProxy

from .base import EntryPoint, BaseApplication


log = logger.get_async('Application')


@EntryPoint.subcommand('test')
class Test(BaseApplication):
    pass


@Test.subcommand('proxies')
class TestProxies(BaseProxy):
    """
    Will be used to test proxies against simple request URLs.
    Not sure if we will maintain this.
    """
    __name__ = 'Test Proxies'


@Test.subcommand('token')
class TestToken(Test):

    __name__ = 'Test Get Token'

    def main(self):
        loop = asyncio.get_event_loop()

        # Token will be None if an exception occured.
        token = self.get_token(loop)
        if not token:
            return


@Test.subcommand('login')
class TestLogin(Test):

    __name__ = 'Test Login'

    collect = cli.Flag("--collect", default=False)

    def main(self, username, password):

        # Default Collect to False
        self._config.update({'proxies': {'pool': {'collect': self.collect}}})

        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        result = loop.run_until_complete(self.test_login(loop, user, password))
        log.info(result.__dict__)

    async def test_login(self, loop, user, password):

        # Not sure if we want to put the proxy handler in the scheduler or not?
        proxy_handler, password_handler = self.post_handlers(user)
        scheduler = await aiojobs.create_scheduler(limit=100)

        try:
            results = await asyncio.gather(
                password_handler.attempt_single_login(loop, scheduler, password),
                proxy_handler.run(loop),
            )
        # Do we really need this catch here?
        except Exception as e:
            loop.call_exception_handler({'exception': e})
            return None
            # log.start('Stopping Proxy Handler due to Exception')
            # await proxy_handler.stop(loop)
            # log.complete('Done Stopping Proxy Handler')
            # loop.call_exception_handler({'exception': e})
        else:
            return results[0]

            # log.start('Stopping Proxy Handler')
            # await proxy_handler.stop(loop)
            # log.complete('Done Stopping Proxy Handler')
