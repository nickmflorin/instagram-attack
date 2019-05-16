import asyncio

from instattack.attack import attack

from .base import EntryPoint, BaseApplication


@EntryPoint.subcommand('attack')
class BaseAttack(BaseApplication):

    async def attempt_attack(self, loop):
        return await attack(loop, self.user, self.config)


@BaseAttack.subcommand('run')
class AttackRun(BaseAttack):

    __name__ = 'Run Attack'

    def main(self, username):
        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        result = loop.run_until_complete(self.attempt_attack(loop))
        if result:
            self.log.info(f'Authenticated User!', extra={
                'password': result.context.password
            })
