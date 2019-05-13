from platform import python_version
from plumbum import cli
import tortoise
import sys

from instattack.lib import validate_log_level

from instattack.core.models import User
from instattack.core.mixins import LoggableMixin


class BaseApplication(cli.Application, LoggableMixin):
    """
    Used so that we can easily extend Instattack without having to worry about
    overriding the main method.

    TODO
    ----
    .cleanup()
    Method performed in cli.Application after all components of main() have
    completed.
    """

    # Even though we are not using the log level internally, and setting
    # it in __main__, we still have to allow this to be a switch otherwise
    # CLI will complain about unknown switch.
    level = cli.SwitchAttr("--level", validate_log_level, default='INFO')

    async def get_user(self, username):
        try:
            user = await User.get(username=username)
        except tortoise.exceptions.DoesNotExist:
            self.log.error(f'User {username} does not exist.')
            return None
        else:
            user.setup()
            return user

    def request_config(self, method=None):
        config = {
            'connection_force_close': self._connection_force_close,
            'connection_keepalive_timeout': self._connection_keepalive_timeout,
            'connection_limit': self._connection_limit[method],
            'connection_limit_per_host': self._connection_limit_per_host[method],
            'session_timeout': self._session_timeout[method],
        }
        if method == 'GET':
            config['token_max_fetch_time'] = self._token_max_fetch_time
        return config

    def broker_config(self, method=None):
        return {
            'max_conn': self._max_conn[method],
            'max_tries': self._max_tries[method],
            'timeout': self._broker_timeout[method],
            # We want to give the broker a sufficiently large limit so that
            # we can manually stop it but still collect enough valid proxies
            # for the pool.
            'limit': int(2.0 * self._pool_limit[method]),
        }

    def pool_config(self, method=None, prepopulate=True, collect=False, log_proxies=False):
        return {
            'min_req_proxy': self._min_req_proxy[method],
            'max_resp_time': self._max_resp_time[method],
            'max_error_rate': self._max_error_rate[method],
            'timeout': self._pool_timeout[method],
            'prepopulate': prepopulate,  # TODO: Make a CLI arg.
            'collect': collect,  # TODO: Make a CLI arg.
            'prepopulate_limit': self._prepopulate_limit[method],
            'limit': self._pool_limit[method],
            'log_proxies': log_proxies,
        }


class Instattack(BaseApplication):

    def main(self, *args):
        self.validate(*args)

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
