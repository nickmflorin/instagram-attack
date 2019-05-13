from plumbum import cli

from instattack.lib import method_switch


"""
TODO:
----
For some things, it might make more sense to load from a configuration file
of some sort.
"""

__all__ = (
    'RequestArgs',
    'ProxyPoolArgs',
    'ProxyBrokerArgs',
    'ProxyArgs',
)


class ConfigArgs(object):
    pass


class RequestArgs(ConfigArgs):

    __group__ = 'Requests'

    # We should probably be using the force close option.
    _connection_force_close = cli.Flag('--connection_force_close')
    _connection_limit = {'GET': 50, 'POST': 200}  # TCP Connector Default is 100
    _connection_limit_per_host = {'GET': 0, 'POST': 0}  # TCP Connector Default is 0
    _session_timeout = {'GET': 5, 'POST': 10}

    _connection_keepalive_timeout = cli.SwitchAttr(
        "--_connection_keepalive_timeout", float,
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


class ProxyPoolArgs(ConfigArgs):

    __group__ = 'Proxy Pool'

    _max_resp_time = {'GET': 8, 'POST': 6}
    _max_error_rate = {'GET': 0.5, 'POST': 0.5}
    _pool_timeout = {'GET': 25, 'POST': 25}
    _min_req_proxy = {'GET': 6, 'POST': 6}

    _pool_limit = {'GET': 50, 'POST': 200}
    _prepopulate_limit = {'GET': 25, 'POST': None}

    @method_switch('pool_limit',
        group=__group__,
        default=_pool_limit,
        help="The maximum number of proxies to maintain in pool.")
    def pool_limit(self, data):
        self._proxy_limit = data

    @method_switch('prepopulate_limit',
        group=__group__,
        default=_prepopulate_limit,
        help="The maximum number of proxies to prepopulate from DB.")
    def prepopulate_limit(self, data):
        self._prepopulate_limit = data

    @method_switch('max_error_rate',
        default=_max_error_rate,
        group=__group__,
        help="Maximum error rate for a given proxy in the pool.")
    def max_error_rate(self, data):
        self._max_error_rate = data

    @method_switch('max_resp_time',
        default=_max_resp_time,
        group=__group__,
        help="Maximum average response time for a given proxy in the pool.")
    def max_resp_time(self, data):
        self._max_resp_time = data

    @method_switch('pool_timeout',
        group=__group__,
        default=_pool_timeout)
    def pool_timeout(self, data):
        self._pool_timeout = data

    @method_switch('min_req_proxy',
        group=__group__,
        default=_min_req_proxy,
        help=(
            "The minimum number of processed requests to estimate the quality "
            "of proxy (in accordance with max_error_rate and max_resp_time)"
        ))
    def min_req_proxy(self, data):
        self._min_req_proxy = data


class ProxyBrokerArgs(ConfigArgs):

    __group__ = "Proxy Broker"

    _max_conn = {'GET': 50, 'POST': 200}
    _max_tries = {'GET': 2, 'POST': 2}
    _broker_timeout = {'GET': 5, 'POST': 5}

    @method_switch('max_conn',
        group=__group__,
        default=_max_conn,
        help="The maximum number of concurrent checks of proxies.")
    def broker_max_conn(self, data):
        self._max_conn = data

    @method_switch('max_tries',
        group=__group__,
        default=_max_tries,
        help="The maximum number of attempts to check a proxy.")
    def broker_max_tries(self, data):
        self._max_tries = data

    @method_switch('broker_timeout',
        group=__group__,
        default=_broker_timeout,
        help="Timeout of a request in seconds")
    def broker_req_timeout(self, data):
        self._broker_timeout = data


class ProxyArgs(ProxyPoolArgs, ProxyBrokerArgs):
    pass


class TokenArgs(ConfigArgs):

    __group__ = 'Instagram Tokens'

    _token_max_fetch_time = cli.SwitchAttr(
        "--token_max_fetch_time", float,
        default=10.0,
        group=__group__,
    )


class PasswordArgs(ConfigArgs):

    __group__ = 'Instagram Passwords'

    _pwlimit = cli.SwitchAttr(
        "--pwlimit", int,
        default=None,
        group=__group__,
    )
