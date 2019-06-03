import asyncio

from cement.utils.version import get_version_banner

from instattack.config import settings
from instattack.app.version import get_version

from .abstract import InstattackController
from .users import UserController
from .interfaces import UserInterface, AttackInterface
from .proxies import ProxyController
from .utils import existing_user_command


VERSION_BANNER = f"{settings.APP_FORMAL_NAME} {get_version()} {get_version_banner()}"


ATTACK_ARGUMENTS = [
    (
        ['-l', '--limit'],
        {
            'default': 100,
            'help': 'Limit the Number of Passwords to Try'
        }
    ),
    (
        ['-nl', '--nolimit'],
        {
            'action': 'store_true',
            'help': 'Do Not Limit the Number of Passwords to Try'
        }
    )
]


class Base(InstattackController, AttackInterface, UserInterface):

    class Meta:
        label = 'base'

        # Text displayed at the top of --help output
        description = settings.APP_FORMAL_NAME

        # Text displayed at the bottom of --help output
        epilog = f'Usage: {settings.APP_NAME} get_user username'

        interfaces = [
            AttackInterface,
            UserInterface
        ]

        handlers = [
            UserController,
            ProxyController,
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

    @existing_user_command(help="Perform Attack Attempt", arguments=ATTACK_ARGUMENTS)
    def attack(self, user):
        """
        Iteratively tries each password for the given user with the provided
        token until a successful response is achieved for each password or
        a successful authenticated response is achieved for any password.

        [x] TODO:
        --------
        Set collect flag to default to False unless specified for login and
        attack modes.
        """
        # TODO: Add Option for Continuing Attack Regardless
        was_authenticated = self.authenticated(user)
        if was_authenticated:
            if not self.proceed('User was already authenticated.'):
                return

        proxy_handler, password_handler = self._attack_handlers()

        limit = None
        if not self.app.pargs.nolimit:
            limit = int(self.app.pargs.limit)

        try:
            results = self.loop.run_until_complete(asyncio.gather(
                password_handler.attack(limit=limit),
                proxy_handler.run(),
            ))
        except Exception as e:
            self.loop.run_until_complete(password_handler.finish_attack())
            self.loop.run_until_complete(proxy_handler.stop())
            raise e
        else:
            # We might not need to stop proxy handler?
            self.loop.run_until_complete(proxy_handler.stop())
            if results[0].authenticated_result:
                self.success(results[0].authenticated_result)
            else:
                self.failure('Not Authenticated')
