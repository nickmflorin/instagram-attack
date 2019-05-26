import asyncio
from plumbum import cli

from instattack import logger
from instattack.src.exceptions import ArgumentError
from instattack.src.cli import EntryPoint, BaseApplication, SelectOperatorApplication

from .models import User


@EntryPoint.subcommand('users')
class UserEntryPoint(BaseApplication):
    pass


class UsersApplication(SelectOperatorApplication):

    limit = cli.SwitchAttr('--limit', int, default=None)


class SingleUserApplication(UsersApplication):

    def main(self, *args):
        loop = asyncio.get_event_loop()

        operator = self.get_operator(*args)
        user = self.get_user(loop, args[1])
        if not user:
            raise ArgumentError('User does not exist.')

        return loop.run_until_complete(operator(loop, user))

    def get_operator(self, *args):
        if len(args) == 0:
            raise ArgumentError('Missing positional arguments.')

        if len(args) == 1:
            if not hasattr(self, 'operation'):
                raise ArgumentError('Missing positional argument.')
            return self.operation
        else:
            method_name = args[0]
            if not hasattr(self, method_name):
                raise ArgumentError('Invalid positional argument.')

            return getattr(self, method_name)


@UserEntryPoint.subcommand('clean')
class CleanUsers(UsersApplication):

    async def directories(self, loop):
        log = logger.get_async(__name__, subname='directories')

        async for user in User.all():
            user.setup()
            await log.complete(f'Cleaned Directory for User {user.username}.')


@UserEntryPoint.subcommand('show')
class ShowUsers(UsersApplication):

    async def operation(self, loop):
        log = logger.get_sync(__name__, subname='operation')

        with log.logging_lines():
            users = await User.all()
            for user in users:
                log.line(user.username)


@UserEntryPoint.subcommand('clear')
class ClearUser(SingleUserApplication):

    async def attempts(self, loop, user):
        log = logger.get_async(__name__, subname='attempts')
        await log.info(f'Clearing User {user.username} Attempts')

        await log.debug('Fetching User Attempts...')
        attempts = await user.get_attempts(limit=self.limit)
        await log.debug('User Attempts Retrieved')

        tasks = []
        for attempt in attempts:
            tasks.append(asyncio.create_task(attempt.delete()))

        await log.start('Deleting Attempts...')
        await asyncio.gather(*tasks)
        if len(tasks) == 0:
            await log.error(f"No attempts to clear for user {user.username}.")
            return

        await log.complete(f"Cleared {len(tasks)} attempts for user {user.username}.")


@UserEntryPoint.subcommand('get')
class GetUser(SingleUserApplication):

    async def passwords(self, loop, user):
        log = logger.get_async(__name__, subname='passwords')
        await log.start(f'Getting User {user.username} Passwords')

        async with log.logging_lines():
            async for item in user.stream_passwords(limit=self.limit):
                await log.line(item)

    async def alterations(self, loop, user):
        log = logger.get_async(__name__, subname='alterations')
        await log.start(f'Getting User {user.username} Alterations')

        async with log.logging_lines():
            async for item in user.stream_alterations(limit=self.limit):
                await log.line(item)

    async def numerics(self, loop, user):
        log = logger.get_async(__name__, subname='numerics')
        await log.start(f'Getting User {user.username} Numerics')

        async with log.logging_lines():
            async for item in user.stream_numerics(limit=self.limit):
                await log.line(item)

    async def attempts(self, loop, user):
        log = logger.get_async(__name__, subname='attempts')
        await log.start(f'Getting User {user.username} Attempts')

        async with log.logging_lines():
            async for attempt in user.stream_attempts(limit=self.limit):
                await log.line(attempt)


@UserEntryPoint.subcommand('generate')
class GenerateUser(SingleUserApplication):

    async def attempts(self, loop, user):
        log = logger.get_sync(__name__, subname='attempts')
        log.start(f'Generating {self.limit} Attempts for User {user.username}.')

        generated = []
        attempts = await user.get_new_attempts(loop, limit=self.limit)

        with log.logging_lines():
            for item in attempts:
                log.line(item)
                generated.append(item)

        assert len(generated) == len(set(generated))
        log.success(f"Generated {len(generated)} Attempts!")


@UserEntryPoint.subcommand('delete')
class DeleteUser(BaseApplication):

    def main(self, username):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.delete_user(loop, username))
        return 1

    async def delete_user(self, loop, username):
        log = logger.get_async(__name__, subname='add_user')

        def delete_user_dir(user):
            log.start('Deleting User Directory...')
            user.teardown()
            log.success('User Directory Deleted')

        user = await self.check_if_user_exists(username)
        if not user:
            user = User(username=username)
            if user.directory().exists():
                log.warning('User does not exist in database.')
                delete_user_dir(user)
            else:
                raise ArgumentError('User does not exist in database.')
        else:
            log.start('Deleting User from DB...')
            await user.delete()
            log.success('User Deleted from DB')

            delete_user_dir(user)


@UserEntryPoint.subcommand('create')
class AddUser(BaseApplication):

    def main(self, username):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.add_user(loop, username))
        return 1

    async def add_user(self, loop, username):
        log = logger.get_async(__name__, subname='add_user')
        user = await self.check_if_user_exists(username)
        if user:
            raise ArgumentError('User already exists.')

        user = await User.create(username=username)
        user.setup()
        log.success(f'Successfully created user {user.username}.')
