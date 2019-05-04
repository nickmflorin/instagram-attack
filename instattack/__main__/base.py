from platform import python_version

import signal
import sys

from plumbum import cli

from instattack.lib.logger import AppLogger, log_handling
from instattack.lib.utils import validate_log_level

from .utils import method_switch


"""
Plumbum Modules That We Should Implement

Plumbum Docs
https://plumbum.readthedocs.io/en/latest/quickref.html

PROGNAME = Custom program name and/or color
VERSION = Custom version
DESCRIPTION = Custom description (or use docstring)
COLOR_GROUPS = Colors of groups (dictionary)
COLOR_USAGE = Custom color for usage statement

Plumbum Progress Bar
Plumbum Colors

Plumbum User Input
plumbum.cli.terminal.readline()
plumbum.cli.terminal.ask()
plumbum.cli.terminal.choose()
plumbum.cli.terminal.prompt()

.cleanup()
Method performed in cli.Application after all components of main() have completed.
"""


class BaseApplication(cli.Application):

    log = AppLogger(__file__)

    # May want to catch other signals too - these are not currently being
    # used, but could probably be expanded upon.
    SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

    level = cli.SwitchAttr("--level", validate_log_level, default='INFO')


class Instattack(BaseApplication):

    def validate(self, *args):
        if int(python_version()[0]) < 3:
            self.log.error('Please use Python 3')
            sys.exit()
        if args:
            self.log.error("Unknown command %r" % (args[0]))
            sys.exit()
        # The nested command will be`None if no sub-command follows
        if not self.nested_command:
            self.log.error("No command given")
            sys.exit()

    @log_handling('self')
    def main(self, *args):
        self.log.warning('Reminder: Look into plumbum colors instead of colorama')
        self.log.warning('Reminder: Look into plumbum progressbar')
        self.validate(*args)


class ConfigArgs(object):
    pass


class RequestArgs(ConfigArgs):

    __group__ = 'Requests'

    # We should probably be using the force close option.
    _connection_force_close = cli.Flag('--connection_force_close')
    _connection_limit = {'GET': 50, 'POST': 200}
    _connection_limit_per_host = {'GET': 0, 'POST': 0}
    _session_timeout = {'GET': 5, 'POST': 10}

    _connection_keepalive_timeout = cli.SwitchAttr(
        "--token_connection_keepalive_timeout", float,
        default=3.0,
        group=__group__,
        help=(
            "Timeout for connection/session reusing after releasing. \n"
            "For disabling keep-alive feature use force_close=True flag."
        )
    )

    @method_switch('connection_limit',
        default=_connection_limit,
        group=__group__,
        help="Total number simultaneous connections for the connector.")
    def connection_limit(self, data):
        self._connection_limit = data

    @method_switch('connection_limit_per_host',
        default=_connection_limit_per_host,
        group=__group__,
        help="Limit simultaneous connections to the same endpoint.")
    def connection_limit_per_host(self, data):
        self._connection_limit_per_host = data

    # This value needs to be higher when we do not have any collected GET proxies
    # stored.
    @method_switch('session_timeout',
        default=_session_timeout,
        group=__group__,
        help="Session timeout for requests.")
    def session_timeout(self, data):
        self._session_timeout = data

    def request_config(self, method=None):
        method = method or self._method
        return {
            'connection_force_close': self._connection_force_close,
            'connection_keepalive_timeout': self._connection_keepalive_timeout,
            'connection_limit': self._connection_limit[method],
            'connection_limit_per_host': self._connection_limit_per_host[method],
            'session_timeout': self._session_timeout[method],
        }
