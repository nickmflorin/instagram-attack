import asyncio
from plumbum import cli

from instattack.src.exceptions import ArgumentError
from instattack.src.users import User

from .base import EntryPoint, UtilityApplication


@EntryPoint.subcommand('users')
class BaseUsers(UtilityApplication):

    def main(self):
        self.silent_shutdown()


@EntryPoint.subcommand('user')
class BaseUser(UtilityApplication):

    def main(self):
        self.silent_shutdown()


@BaseUsers.subcommand('clean')
class CleanUsers(UtilityApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.clean())

    async def clean(self):
        async for user in User.all():
            user.setup()
            self.log.info(f'Cleaned Directory for User {user.username}.')


@BaseUsers.subcommand('show')
class UsersShowApplication(UtilityApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.users(loop))

    async def users(self, loop):
        with self.log.logging_lines():
            users = await User.all()
            for user in users:
                self.log.line(user.username)


@BaseUser.subcommand('show')
class UserShowApplication(UtilityApplication):

    limit = cli.SwitchAttr('--limit', int, default=None)

    def main(self, *args):
        if len(args) != 2:
            raise ArgumentError('Must provide username and items to show.')

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, *args))

    async def operation(self, loop, *args):
        method = getattr(self, args[0], None)
        if not method:
            self.log.error(f'Invalid argument {args[0]}.')
            return
        try:
            username = args[1]
        except IndexError:
            self.log.error('Must provide username.')
            return
        else:
            user = await self.get_user(username)
            if not user:
                self.log.error('User does not exist.')
                return

            await method(loop, user)

    async def passwords(self, loop, user):
        self.log.start(f'Showing User {user.username} Passwords')

        with self.log.logging_lines():
            async for item in user.get_passwords(limit=self.limit):
                self.log.line(item)

    async def alterations(self, loop, user):
        self.log.start(f'Showing User {user.username} Alterations')

        with self.log.logging_lines():
            async for item in user.get_alterations(limit=self.limit):
                self.log.line(item)

    async def numerics(self, loop, user):
        self.log.start(f'Showing User {user.username} Numerics')

        with self.log.logging_lines():
            async for item in user.get_numerics(limit=self.limit):
                self.log.line(item)

    async def attempts(self, loop, user):
        self.log.start(f'Showing User {user.username} Attempts')

        if self.new:
            generated = []
            with self.log.logging_lines():
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
class DeleteUser(UtilityApplication):

    def main(self, username):

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, username))

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
class AddUser(UtilityApplication):

    def main(self, username):

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, username))

    async def operation(self, loop, username):
        user = await self.check_if_user_exists(username)
        if user:
            self.log.error('User already exists.')
            return

        user = await User.create(username=username)
        self.log.success(f'Successfully created user {user.username}.')
