#!/usr/bin/env python3
from platform import python_version

import signal
import sys

from plumbum import cli

from instattack.conf.utils import validate_log_level
from instattack.logger import AppLogger, log_handling

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

    _method = 'GET'

    @cli.switch("--method", cli.Set("GET", "POST", case_sensitive=False))
    def method(self, method):
        self._method = method.upper()
        return self._method


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
        self.validate(*args)


class ConfigArgs(object):

    def _conditional_set(self, name, value, conditional):
        if hasattr(self, conditional):
            if not hasattr(self, name):
                setattr(self, '_%s' % name, value[getattr(self, conditional)])
            else:
                setattr(self, name, value[getattr(self, conditional)])
        else:
            if not hasattr(self, name):
                setattr(self, '_%s' % name, value)
            else:
                setattr(self, name, value)


class ProxyPoolArgs(ConfigArgs):

    __group__ = 'Proxy Pool'

    _max_resp_time = None
    _max_error_rate = None
    _proxy_queue_timeout = None
    _proxy_pool_timeout = None
    _pool_min_req_proxy = None

    @method_switch('max_error_rate',
        default={'GET': 0.5, 'POST': 0.5},
        group=__group__,
        help="Maximum error rate for a given proxy in the pool.")
    def max_error_rate(self, data):
        self._conditional_set('_max_error_rate', data, '_method')

    @method_switch('max_resp_time',
        default={'GET': 8, 'POST': 6},
        group=__group__,
        help="Maximum average response time for a given proxy in the pool.")
    def max_resp_time(self, data):
        self._conditional_set('_max_resp_time', data, '_method')

    @method_switch('proxy_queue_timeout',
        group=__group__,
        default={'GET': 8, 'POST': 8})
    def proxy_queue_timeout(self, data):
        self._conditional_set('_proxy_queue_timeout', data, '_method')

    @method_switch('proxy_pool_timeout',
        group=__group__,
        default={'GET': 25, 'POST': 25})
    def proxy_pool_timeout(self, data):
        self._conditional_set('_proxy_pool_timeout', data, '_method')

    @method_switch('pool_min_req_proxy',
        group=__group__,
        default={'GET': 3, 'POST': 3},
        help=(
            "The minimum number of processed requests to estimate the quality "
            "of proxy (in accordance with max_error_rate and max_resp_time)"
        ))
    def pool_min_req_proxy(self, data):
        self._conditional_set('_pool_min_req_proxy', data, '_method')


class RequestArgs(ConfigArgs):

    __group__ = 'Requests'

    # We should probably be using the force close option.
    _connection_force_close = cli.Flag('--connection_force_close')

    _connection_keepalive_timeout = cli.SwitchAttr(
        "--token_connection_keepalive_timeout", float,
        default=3.0,
        group=__group__,
        help=(
            "Timeout for connection/session reusing after releasing. \n"
            "For disabling keep-alive feature use force_close=True flag."
        )
    )
    _connection_limit = None
    _connection_limit_per_host = None
    _session_timeout = None

    @method_switch('connection_limit',
        default={'GET': 50, 'POST': 200},
        group=__group__,
        help="Total number simultaneous connections for the connector.")
    def connection_limit(self, data):
        self._conditional_set('connection_limit', data, '_method')

    @method_switch('connection_limit_per_host',
        default={'GET': 0, 'POST': 0},
        group=__group__,
        help="Limit simultaneous connections to the same endpoint.")
    def connection_limit_per_host(self, data):
        self._conditional_set('connection_limit_per_host', data, '_method')

    # This value needs to be higher when we do not have any collected GET proxies
    # stored.
    @method_switch('session_timeout',
        default={'GET': 5, 'POST': 10},
        group=__group__,
        help="Session timeout for requests.")
    def session_timeout(self, data):
        self._conditional_set('session_timeout', data, '_method')
