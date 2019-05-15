import asyncio
from plumbum import cli

from instattack.core.users import User

from .base import Instattack, BaseApplication


@Instattack.subcommand('users')
class BaseUsers(BaseApplication):
    pass


@Instattack.subcommand('user')
class BaseUser(BaseApplication):
    pass


class UserOperation(BaseApplication):

    def main(self, *args):
        self.silent_shutdown()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, *args))


@BaseUsers.subcommand('clean')
class CleanUsers(BaseUsers):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.clean())

    async def clean(self):
        async for user in User.all():
            user.setup()
            self.log.info(f'Cleaned Directory for User {user.username}.')


@BaseUser.subcommand('show')
class UsersShowApplication(UserOperation):

    limit = cli.SwitchAttr('--limit', int, default=None)
    new = cli.Flag('--new', default=False)

    @property
    def methods(self):
        return {
            'passwords': self.passwords,
            'alterations': self.alterations,
            'numerics': self.numerics,
            'attempts': self.attempts,
        }

    async def operation(self, loop, item, username):
        method = self.methods.get(item)
        if not method:
            self.log.error(f'Invalid argument {item}.')
            return

        user = await self.get_user(username)
        if not user:
            self.log.error('User does not exist.')
            return

        await method(loop, user)

    async def passwords(self, loop, user):
        self.log.start(f'Showing User {user.username} Passwords')

        self.log.before_lines()
        async for item in user.get_passwords(limit=self.limit):
            self.log.line(item)

    async def alterations(self, loop, user):
        self.log.start(f'Showing User {user.username} Alterations')

        self.log.before_lines()
        async for item in user.get_alterations(limit=self.limit):
            self.log.line(item)

    async def numerics(self, loop, user):
        self.log.start(f'Showing User {user.username} Numerics')

        self.log.before_lines()
        async for item in user.get_numerics(limit=self.limit):
            self.log.line(item)

    async def attempts(self, loop, user):
        self.log.start(f'Showing User {user.username} Attempts')

        if self.new:
            generated = []
            self.log.before_lines()
            async for item in user.generate_attempts(loop, limit=self.limit):
                self.log.line(item)
                generated.append(item)

            assert len(generated) == len(set(generated))
            self.log.simple(f"Generated {len(generated)} Attempts!")

        else:
            attempts = user.get_attempts(limit=self.limit)
            if len(attempts) == 0:
                self.log.info(f"No attempts for user {user.username}.")
            else:
                self.log.line_by_line(attempts)


@BaseUser.subcommand('delete')
class DeleteUser(UserOperation):

    async def operation(self, loop, username):
        user = await self.get_user(username)
        if not user:
            self.log.error('User does not exist.')
            return

        self.log.start('Removing user directory...')
        user.teardown()
        self.log.start('Deleting user from database...')
        await user.delete()
        self.log.success('Success.')


@BaseUser.subcommand('add')
class AddUser(UserOperation):

    async def operation(self, loop, username):
        user = await self.get_user(username)
        if user:
            self.log.error('User already exists.')
            return

        user = await User.create(username=username)
        self.log.info(f'Successfully created user {user.username}.')
