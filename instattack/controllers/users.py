import asyncio

from cement import ex, Interface

import tortoise

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
