import asyncio
from abc import abstractmethod

from cement import Controller, ex, Interface
from cement.utils.version import get_version_banner

import tortoise

from instattack.app.base import HandlerMixin
from instattack.app.version import get_version
from instattack.app.users.models import User


APP_NAME = "Instattack"
VERSION_BANNER = f"{APP_NAME} {get_version()} {get_version_banner()}"


class UserInterface(Interface):
    class Meta:
        interface = 'user'

    @abstractmethod
    async def _get_users(self, loop):
        return await User.all()

    @abstractmethod
    def get_user(self, loop, username):

        async def _get_user(username):
            async with self.async_logger('get_user') as log:
                try:
                    user = await User.get(username=username)
                except tortoise.exceptions.DoesNotExist:
                    await log.error(f'User {username} does not exist.')
                    return None
                else:
                    user.setup()
                    return user

        return loop.run_until_complete(_get_user(username))

    @abstractmethod
    async def check_if_user_exists(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            return None
        else:
            return user


class UserController(Controller, HandlerMixin):

    class Meta:
        label = 'user'

        interfaces = [
            UserInterface,
        ]

    def get_user(self):
        username = self.app.pargs.username


class Base(Controller, HandlerMixin):
    class Meta:
        label = 'base'

        # Text displayed at the top of --help output
        description = APP_NAME

        # Text displayed at the bottom of --help output
        epilog = 'Usage: instattack get_user username'

        handlers = [
            UserController,
        ]

        # Controller Level Arguments. ex: 'instattack --version'
        arguments = [
            (
                ['-v', '--version'],
                {'action': 'version', 'version': VERSION_BANNER}
            ),
        ]

    def _default(self):
        """
        Default Action if No Sub-Command Passed
        """
        self.app.args.print_help()

    @ex(help='Display All Users')
    def get_users(self):
        data = {'users': []}

        loop = asyncio.get_event_loop()
        users = loop.run_until_complete(self._get_users(loop))
        for user in users:
            data['users'].append(user.__dict__)

        self.app.render(data, 'get_users.jinja2')

    @ex(
        help='Display Information for User',
        arguments=[
            (['username'], {'help': 'Username'}),
        ],
    )


# @UserEntryPoint.subcommand('get')
# class GetUser(SingleUserApplication):

#     async def passwords(self, loop, user):
#         async with self.async_logger('passwords') as log:
#             await log.start(f'Getting User {user.username} Passwords')

#             async with log.logging_lines():
#                 async for item in user.stream_passwords(limit=self.limit):
#                     await log.line(item)

#     async def alterations(self, loop, user):
#         async with self.async_logger('alterations') as log:
#             await log.start(f'Getting User {user.username} Alterations')

#             async with log.logging_lines():
#                 async for item in user.stream_alterations(limit=self.limit):
#                     await log.line(item)

#     async def numerics(self, loop, user):
#         async with self.async_logger('numerics') as log:
#             await log.start(f'Getting User {user.username} Numerics')

#             async with log.logging_lines():
#                 async for item in user.stream_numerics(limit=self.limit):
#                     await log.line(item)

#     async def attempts(self, loop, user):
#         async with self.async_logger('attempts') as log:
#             await log.start(f'Getting User {user.username} Attempts')

#             async with log.logging_lines():
#                 async for attempt in user.stream_attempts(limit=self.limit):
#                     await log.line(attempt)
