from cement.utils.version import get_version_banner

from instattack import settings
from instattack.lib import logger

from instattack.core.handlers import AttackHandler

from .abstract import InstattackController
from .users import UserController
from .interfaces import UserInterface
from .proxies import ProxyController
from .utils import existing_user_command


VERSION_BANNER = f"{settings.FORMAL_NAME} {settings.VERSION} {get_version_banner()}"


class Base(InstattackController, UserInterface):

    class Meta:
        label = 'base'

        # Text displayed at the top of --help output
        description = settings.FORMAL_NAME

        # Text displayed at the bottom of --help output
        epilog = f'Usage: {settings.NAME} get_user username'

        interfaces = [
            UserInterface
        ]

        handlers = [
            UserController,
            ProxyController,
        ]

        # Controller Level Arguments. ex: 'instattack --version'
        arguments = [
            (['-v', '--version'],
             dict(version=VERSION_BANNER, action='version')),
            (['-l', '--level'],
             dict(help='Override the Logging Level', action='store')),
            (['--simple'],
             dict(help='Set the logging mode to simple.', action='store_true')),
            (['--diagnostics'],
             dict(help='Run diagnostics mode.', action='store_true')),
            (['--request_errors'],
             dict(help='Log Request Errors', action='store_true')),
        ]

    def _post_argument_parsing(self):
        """
        Override the logging level if provided and set the logging class if
        the logging mode is one other than the default.
        """
        mode = None
        if self.app.pargs.diagnostics:
            mode = 'diagnostics'
        elif self.app.pargs.simple:
            mode = 'simple'

        logger.configure(mode=mode, level=self.app.pargs.level)

    def _default(self):
        """
        Default Action if No Sub-Command Passed
        """
        self.app.args.print_help()

    @existing_user_command(
        help="Perform Attack Attempt",
        arguments=[
            (['-l', '--limit'],
             dict(help='Limit the Number of Passwords to Try', default=100, type=int)),
            (['-nl', '--nolimit'],
             dict(help='Do Not Limit the Number of Passwords to Try', action='store_true')),  # noqa
        ]
    )
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
        was_authenticated = self.authenticated(user)
        if was_authenticated:
            if not self.proceed('User was already authenticated.'):
                return

        attack = AttackHandler(self.loop)

        limit = None
        if not self.app.pargs.nolimit:
            limit = int(self.app.pargs.limit)

        result = self.loop.run_until_complete(attack.attack(limit=limit))
        if result.authenticated_result:
            self.success(result.authenticated_result)
        else:
            self.failure('Not Authenticated')
