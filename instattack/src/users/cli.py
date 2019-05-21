import asyncio
from plumbum import cli

from instattack.src.cli import EntryPoint, BaseApplication

from .models import User


@EntryPoint.subcommand('users')
class UsersEntryPoint(BaseApplication):

    def main(self, *args):
        self._config.update({'silent_shutdown': True})


class UsersApplication(BaseApplication):
    pass


@UsersEntryPoint.subcommand('clean')
class CleanUsers(UsersApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.clean())

    async def clean(self):
        async for user in User.all():
            user.setup()
            self.log.info(f'Cleaned Directory for User {user.username}.')


@UsersEntryPoint.subcommand('show')
class ShowUsers(UsersApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.users(loop))

    async def users(self, loop):
        with self.log.logging_lines():
            users = await User.all()
            for user in users:
                self.log.line(user.username)


@EntryPoint.subcommand('user')
class UserEntryPoint(BaseApplication):

    def main(self, *args):
        self._config.update({'silent_shutdown': True})


class UserApplication(BaseApplication):

    limit = cli.SwitchAttr('--limit', int, default=None)

    def main(self, *args):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, *args))

    async def operation(self, loop, *args):
        try:
            method = getattr(self, args[0])
        except (IndexError, AttributeError):
            self.log.error('Must provide items to show.')
        else:
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


@UserEntryPoint.subcommand('clear')
class ClearUser(UserApplication):

    async def attempts(self, loop, user):
        self.log.start(f'Clearing User {user.username} Attempts')

        attempts = await user.get_attempts(limit=self.limit)

        tasks = []
        for attempt in attempts:
            tasks.append(asyncio.create_task(attempt.delete()))

        await asyncio.gather(*tasks)
        if len(tasks) == 0:
            self.log.error(f"No attempts to clear for user {user.username}.")
        else:
            self.log.success(f"Cleared {len(tasks)} attempts for user {user.username}.")


@UserEntryPoint.subcommand('show')
class ShowUser(UserApplication):

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

        attempts = user.get_attempts(limit=self.limit)

        if len(attempts) == 0:
            self.log.info(f"No attempts for user {user.username}.")
        else:
            self.log.line_by_line(attempts)


@UserEntryPoint.subcommand('generate')
class UserGenerate(UserApplication):

    async def attempts(self, loop, user):
        self.log.start(f'Generating {self.limit} Attempts for User {user.username}.')

        generated = []
        with self.log.logging_lines():
            async for item in user.generate_attempts(loop, limit=self.limit):
                self.log.line(item)
                generated.append(item)

            assert len(generated) == len(set(generated))
            self.log.simple(f"Generated {len(generated)} Attempts!")


@UserEntryPoint.subcommand('delete')
class DeleteUser(UserApplication):

    async def operation(self, loop, username):
        user = await self.check_if_user_exists(username)
        if not user:
            self.log.warning('User does not exist in database.')

            user = User(username=username)
            if user.directory().exists():
                self.log.start('Deleting User Directory...')
                user.teardown()
                self.log.complete('User Directory Deleted')
        else:
            self.log.start('Deleting User from DB...')
            await user.delete()
            self.log.complete('User Deleted from DB')

            self.log.start('Deleting User Directory...')
            user.teardown()
            self.log.complete('User Directory Deleted')


@UserEntryPoint.subcommand('add')
class AddUser(UserApplication):

    async def operation(self, loop, username):
        user = await self.check_if_user_exists(username)
        if user:
            self.log.error('User already exists.')
            return

        user = await User.create(username=username)
        self.log.success(f'Successfully created user {user.username}.')
