from plumbum import cli

from instattack.core.users import User

from .base import Instattack, BaseApplication


@Instattack.subcommand('users')
class UsersApplication(BaseApplication):
    pass


@UsersApplication.subcommand('clean')
class UsersCleanApplication(UsersApplication):

    def main(self):
        with self.loop_session() as loop:
            loop.run_until_complete(self.clean())

    async def clean(self):
        async for user in User.all():
            user.setup()
            self.log.info(f'Cleaned Directory for User {user.username}.')


@UsersApplication.subcommand('show')
class UsersShowApplication(UsersApplication):

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

    def main(self, item, username):
        with self.loop_session() as loop:
            loop.run_until_complete(self.operation(loop, item, username))

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
        self.log.before_lines()
        async for item in user.get_passwords(limit=self.limit):
            self.log.line(item)

    async def alterations(self, loop, user):
        self.log.before_lines()
        async for item in user.get_alterations(limit=self.limit):
            self.log.line(item)

    async def numerics(self, loop, user):
        self.log.before_lines()
        async for item in user.get_numerics(limit=self.limit):
            self.log.line(item)

    async def attempts(self, loop, user):
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


class UserOperation(UsersApplication):

    def main(self, *args):
        if len(args) != 1:
            self.log.error('Must provide single username argument.')
            return

        username = args[0]
        with self.loop_session() as loop:
            loop.run_until_complete(self.operation(username))


@UsersApplication.subcommand('delete')
class DeleteUser(UserOperation):

    async def operation(self, username):
        user = await self.get_user(username)
        if not user:
            self.log.error('User does not exist.')
        else:
            self.log.info('Removing user directory...')
            user.teardown()
            self.log.info('Deleting user from database...')
            await user.delete()
            self.log.info('Success.')


@UsersApplication.subcommand('add')
class AddUser(UserOperation):

    async def operation(self, username):
        user = await self.get_user(username)
        if not user:
            user = await User.create(username=username)
            self.log.info(f'Successfully created user {user.username}.')
        else:
            self.log.error('User already exists.')
