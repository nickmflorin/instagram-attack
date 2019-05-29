from cement.utils.version import get_version_banner

from instattack.app import settings
from instattack.app.version import get_version

from .abstract import InstattackController
from .users import UserController


APP_NAME = settings.APP_NAME.title()
VERSION_BANNER = f"{APP_NAME} {get_version()} {get_version_banner()}"


class Base(InstattackController):

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
