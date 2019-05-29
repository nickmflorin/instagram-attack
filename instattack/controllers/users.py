import asyncio

from cement import ex, Interface

import tortoise

from instattack.app import settings
from instattack.app.exceptions import UserDoesNotExist, UserExists
from instattack.app.users import User

from .abstract import InstattackController


# @UserEntryPoint.subcommand('clean')
# class CleanUsers(UsersApplication):

#     async def directories(self, loop):
#         async with self.async_logger('directories') as log:
#             async for user in User.all():
#                 user.setup()
#                 await log.complete(f'Cleaned Directory for User {user.username}.')


# @UserEntryPoint.subcommand('clear')
# class ClearUser(SingleUserApplication):

#     async def attempts(self, loop, user):
#         async with self.async_logger('attempts') as log:
#             await log.info(f'Clearing User {user.username} Attempts')

#             await log.debug('Fetching User Attempts...')
#             attempts = await user.get_attempts(limit=self.limit)
#             await log.debug('User Attempts Retrieved')

#             tasks = []
#             for attempt in attempts:
#                 tasks.append(asyncio.create_task(attempt.delete()))

#             await log.start('Deleting Attempts...')
#             await asyncio.gather(*tasks)
#             if len(tasks) == 0:
#                 await log.error(f"No attempts to clear for user {user.username}.")
#                 return

#             await log.complete(f"Cleared {len(tasks)} attempts for user {user.username}.")


class UserInterface(Interface):

    class Meta:
        interface = 'user'

    async def _get_users(self, loop):
        return await User.all()

    async def _check_if_user_exists(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            return None
        else:
            return user

    async def _create_user(self, username):
        try:
            return await User.create(username=username)
        except tortoise.exceptions.IntegrityError:
            raise UserExists(username)

    async def _delete_user(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            raise UserDoesNotExist(username)
        else:
            await user.delete()

    async def _get_user(self, username):
        try:
            return await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            raise UserDoesNotExist(username)


class ShowUserDataController(InstattackController, UserInterface):

    class Meta:
        label = 'user_data'
        stacked_on = 'users'
        stacked_type = 'nested'

        interfaces = [
            UserInterface,
        ]

    @ex(
        help='Show User Base Passwords',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def passwords(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        passwords = user.get_passwords()

        data = {'title': 'Passwords', 'data': passwords}
        self.app.render(data, 'user_data.jinja2')

    @ex(
        help='Show User Base Alterations',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def alterations(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        alterations = user.get_alterations()

        data = {'title': 'Alterations', 'data': alterations}
        self.app.render(data, 'user_data.jinja2')

    @ex(
        help='Show User Numeric Alterations',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def numerics(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        numerics = user.get_numerics()

        data = {'title': 'User Numeric Alterations', 'data': numerics}
        self.app.render(data, 'user_data.jinja2')

    @ex(
        help='Show User Historical Password Atttempts',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def attempts(self):

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(self.app.pargs.username))
        attempts = loop.run_until_complete(user.get_attempts())

        data = {'title': 'User Attempts', 'data': attempts}
        self.app.render(data, 'user_data.jinja2')


class UserController(InstattackController, UserInterface):

    class Meta:
        label = 'users'
        stacked_on = 'base'
        stacked_type = 'nested'

        interfaces = [
            UserInterface,
        ]

        handlers = [
            ShowUserDataController
        ]

    @ex(
        help='Create a New User',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def create(self):
        username = self.app.pargs.username

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._create_user(username))
        attempts = loop.run_until_complete(user.get_attempts())

        data = {'user': {
            'id': user.id,
            'username': user.username,
            'num_attempts': len(attempts),
            'date_created': user.date_created,
            'num_passwords': len(user.get_passwords()),
            'num_numerics': len(user.get_numerics()),
            'num_alterations': len(user.get_alterations())
        }}
        self.app.render(data, 'user.jinja2')

    @ex(
        help='Delete User',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def delete(self):
        username = self.app.pargs.username

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._delete_user(username))

        self.success(f"User {username} Successfully Deleted")

    @ex(
        help='Display Information for User',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )
    def get(self):
        username = self.app.pargs.username

        loop = asyncio.get_event_loop()
        user = loop.run_until_complete(self._get_user(username))

        data = {'user': {
            'id': user.id,
            'username': user.username,
            'num_attempts': len(user.get_attempts()),
            'date_created': user.date_created,
            'num_passwords': len(user.get_passwords()),
            'num_numerics': len(user.get_numerics()),
            'num_alterations': len(user.get_alterations())
        }}
        self.app.render(data, 'user.jinja2')

    @ex(help='Display All Users')
    def get_all(self):
        data = {'users': []}

        loop = asyncio.get_event_loop()
        users = loop.run_until_complete(self._get_users(loop))
        for user in users:
            data['users'].append(user.__dict__)

        self.app.render(data, 'users.jinja2')

    @ex(help='Clean User Directory for Active and Deleted Users')
    def clean(self):
        """
        First, loops over current users and ensures that their directory
        and files are present.  Then, looks in the user directory for any
        users that do not exist anymore and deletes those files.
        """
        loop = asyncio.get_event_loop()
        users = loop.run_until_complete(self._get_users(loop))
        for user in users:
            # This really shouldn't happen often, since we do this on save.
            if not user.directory.exists():
                user.initialize_directory()

        directory = settings.USER_PATH
        for user_dir in directory.iterdir():
            if user_dir.is_file():
                print(f'Deleting File {user_dir.name}')
                user_dir.delete()
            else:
                # Remove Directory if User Does Not Exist
                if user_dir.name not in [user.username for user in users]:
                    print(f'Deleting Leftover Directory for {user_dir.name}')
                    user_dir.delete()
                else:
                    user = [usr for usr in users if usr.username == user_dir.name][0]

                    # Make Sure All Files Present if User Exists
                    for file in User.FILES:
                        pt = user.file_path(file)
                        if not pt.exists() or not pt.is_file():
                            print(f'File {pt.name} Missing for User {user.username}')
                            pt.touch()

                    # Make Sure No Other Files Present
                    for others in user_dir.iterdir():
                        if not user_dir.is_file() or user_dir.name not in User.FILES:
                            print(f'Warning: Found Unidentified Item {user_dir.name}')
