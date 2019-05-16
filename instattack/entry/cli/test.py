import asyncio

from instattack.attack import get_token

from .proxies import BaseProxy
from .attack import BaseAttack
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
class TestToken(BaseAttack):

    __name__ = 'Test Get Token'

    def main(self):
        loop = asyncio.get_event_loop()

        # Token will be None if an exception occured.
        token = self.get_token(loop)
        if not token:
            return


@Test.subcommand('login')
class TestLogin(BaseAttack):

    __name__ = 'Test Login'

    def main(self, username, password):
        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        post_proxy_handler, password_handler = self.post_handlers(user)
        try:
            results = loop.run_until_complete(asyncio.gather(
                password_handler.attempt_single_login(loop, password),
                post_proxy_handler.run(loop)
            ))
        except Exception as e:
            if not post_proxy_handler._stopped:
                post_proxy_handler.broker.stop(loop)
            loop.call_exception_handler({'exception': e})

        else:
            result = results[0]
            self.log.success(result)
