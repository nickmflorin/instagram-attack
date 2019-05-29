import asyncio

from cement import Controller, ex
from cement.utils.version import get_version_banner

import tortoise

from instattack.lib import logger
from instattack.app.version import get_version
from instattack.app.users.models import User


APP_NAME = "Instattack"
VERSION_BANNER = f"{APP_NAME} {get_version()} {get_version_banner()}"


class Base(Controller):
    class Meta:
        label = 'base'

        # Text displayed at the top of --help output
        description = APP_NAME

        # Text displayed at the bottom of --help output
        epilog = 'Usage: instattack get_user username'

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

    async def _get_users(self, loop):
        return await User.all()

    def get_user(self, loop, username):

        async def _get_user(username):
            log = logger.get_async(__name__, subname='get_user')

            try:
                user = await User.get(username=username)
            except tortoise.exceptions.DoesNotExist:
                await log.error(f'User {username} does not exist.')
                return None
            else:
                user.setup()
                return user

        return loop.run_until_complete(_get_user(username))

    async def check_if_user_exists(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            return None
        else:
            return user

    @ex(help='Display All Users')
    def get_users(self):
        data = {'users': []}

        loop = asyncio.get_event_loop()
        users = loop.run_until_complete(self._get_users(loop))
        for user in users:
            data['users'].append(user.__dict__)

        self.app.render(data, 'get_users.jinja2')
