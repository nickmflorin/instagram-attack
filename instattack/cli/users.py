import tortoise

from lib import log_handling

from instattack.models import User

from .base import Instattack, BaseApplication

# TODO:
# Add a command to remove users and delete directory.


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
    def main(self, username):
        with self.loop_session() as loop:
            loop.run_until_complete(self.clean(username))

    async def clean(self, username):
        user = await self.get_user(username)
        if not user:
            self.log.error('User does not exist.')
            return
        user.setup()
        return


@UsersApplication.subcommand('show')
class UsersShowApplication(UsersApplication):
    pass


class UserOperation(UsersApplication):

    @log_handling('self')
    def main(self, *args):
        if len(args) != 1:
            self.log.error('Must provide single username argument.')
            return

        username = args[0]
        with self.loop_session() as loop:
            loop.run_until_complete(self.operation(username))


@UsersShowApplication.subcommand('passwords')
class ShowUserPasswords(UserOperation):

    async def operation(self, username):
        user = await self.get_user(username)
        if not user:
            self.log.error('User does not exist.')
            return

        async for pw in user.get_passwords():
            self.log.info(pw)


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
