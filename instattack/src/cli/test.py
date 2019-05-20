import asyncio
from plumbum import cli

from instattack.src.proxies.cli import BaseProxy
from .base import EntryPoint, BaseApplication


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

        proxy_handler, password_handler = self.post_handlers(user)

        try:
            results = loop.run_until_complete(asyncio.gather(
                password_handler.attempt_single_login(loop, password),
                proxy_handler.run(loop)
            ))
        except Exception as e:
            loop.run_until_complete(proxy_handler.stop(loop))
            loop.call_exception_handler({'exception': e})
        else:
            if results[0].authorized:
                self.log.success(results[0])
            else:
                self.log.error(results[0])
            loop.run_until_complete(proxy_handler.stop(loop))
