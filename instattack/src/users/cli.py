import asyncio
from plumbum import cli

from instattack.src.cli import EntryPoint, BaseApplication

from .models import User


@EntryPoint.subcommand('users')
class BaseUsers(BaseApplication):

    def main(self, *args):
        self._config.update({'silent_shutdown': True})


@EntryPoint.subcommand('user')
class BaseUser(BaseApplication):

    def main(self, *args):
        self._config.update({'silent_shutdown': True})


@BaseUsers.subcommand('clean')
class CleanUsers(BaseApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.clean())

    async def clean(self):
        async for user in User.all():
            user.setup()
            self.log.info(f'Cleaned Directory for User {user.username}.')


@BaseUsers.subcommand('show')
class ShowUsers(BaseApplication):

    def main(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.users(loop))

    async def users(self, loop):
        with self.log.logging_lines():
            users = await User.all()
            for user in users:
                self.log.line(user.username)


@BaseUser.subcommand('show')
class ShowUser(BaseApplication):

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


@BaseUser.subcommand('generate')
class UserGenerate(BaseApplication):

    limit = cli.SwitchAttr('--limit', int, default=100)

    def main(self, *args):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, *args))

    async def operation(self, loop, *args):
        try:
            method = getattr(self, args[0])
        except (IndexError, AttributeError):
            self.log.error('Must provide items to generate.')
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

    async def attempts(self, loop, user):
        self.log.start(f'Generating {self.limit} Attempts for User {user.username}.')

        generated = []
        with self.log.logging_lines():
            async for item in user.generate_attempts(loop, limit=self.limit):
                self.log.line(item)
                generated.append(item)

            assert len(generated) == len(set(generated))
            self.log.simple(f"Generated {len(generated)} Attempts!")


@BaseUser.subcommand('delete')
class DeleteUser(BaseApplication):

    def main(self, username):

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.operation(loop, username))

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


@BaseUser.subcommand('add')
class AddUser(BaseApplication):

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
