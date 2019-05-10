from plumbum import cli
import tortoise
import sys

from lib import log_handling

from instattack.models import User

from .base import Instattack, BaseApplication


@Instattack.subcommand('users')
class UsersApplication(BaseApplication):

    async def get_user(self, username):
        try:
            return await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            self.log.error(f'User {username} does not exist.')
            return None


@UsersApplication.subcommand('clean')
class UsersCleanApplication(UsersApplication):

    @log_handling('self')
    def main(self):
        with self.loop_session() as loop:
            loop.run_until_complete(self.clean())

    async def clean(self):
        async for user in User.all():
            user.setup()
            self.log.notice(f'Cleaned Directory for User {user.username}.')


@UsersApplication.subcommand('show')
class UsersShowApplication(UsersApplication):

    limit = cli.SwitchAttr('--limit', int, default=None)
    new = cli.Flag('--new', default=False)

    @property
    def methods(self):
        return {
            'passwords': self.passwords,
            'alterations': self.alterations,
            'numbers': self.numbers,
            'attempts': self.attempts,
        }

    @log_handling('self')
    def main(self, item, username):
        with self.loop_session() as loop:
            loop.run_until_complete(self.operation(item, username))

    async def operation(self, item, username):
        method = self.methods.get(item)
        if not method:
            self.log.error(f'Invalid argument {item}.')
            return

        user = await self.get_user(username)
        if not user:
            self.log.error('User does not exist.')
            return

        await method(user)

    async def passwords(self, user):
        async for item in user.get_passwords(limit=self.limit):
            sys.stdout.write(item)

    async def alterations(self, user):
        async for item in user.get_alterations(limit=self.limit):
            sys.stdout.write(item)

    async def numbers(self, user):
        async for item in user.get_numerics(limit=self.limit):
            sys.stdout.write(item)

    async def attempts(self, user):
        if self.new:
            generated = []
            async for item in user.generate_attempts(limit=self.limit):
                # self.log.bare(item)
                generated.append(item)

            # Only until we can handle logging the iterable form with indices.
            self.log.line_by_line(generated)

            assert len(generated) == len(set(generated))
            self.log.simple(f"Generated {len(generated)} Attempts!")

        else:
            attempts = user.get_attempts(limit=self.limit)
            if len(attempts) == 0:
                self.log.info(f"No attempts for user {user.username}.")
            else:
                self.log.line_by_line(attempts)


class UserOperation(UsersApplication):

    @log_handling('self')
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
            self.log.notice('Success.')


@UsersApplication.subcommand('add')
class AddUser(UserOperation):

    async def operation(self, username):
        user = await self.get_user(username)
        if not user:
            user = await User.create(username=username)
            self.log.notice(f'Successfully created user {user.username}.')
        else:
            self.log.error('User already exists.')
