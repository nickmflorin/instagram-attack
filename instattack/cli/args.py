from plumbum import cli

from .utils import method_switch


__all__ = (
    'RequestArgs',
    'ProxyPoolArgs',
    'ProxyBrokerArgs',
    'ProxyFinderArgs',
    'ProxyArgs',
)


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


class ProxyPoolArgs(ConfigArgs):

    __group__ = 'Proxy Pool'

    _pool_max_resp_time = {'GET': 8, 'POST': 6}
    _pool_max_error_rate = {'GET': 0.5, 'POST': 0.5}
    _proxy_pool_timeout = {'GET': 25, 'POST': 25}
    _pool_min_req_proxy = {'GET': 3, 'POST': 3}

    @method_switch('pool_max_error_rate',
        default=_pool_max_error_rate,
        group=__group__,
        help="Maximum error rate for a given proxy in the pool.")
    def pool_max_error_rate(self, data):
        self._pool_max_error_rate = data

    @method_switch('pool_max_resp_time',
        default=_pool_max_resp_time,
        group=__group__,
        help="Maximum average response time for a given proxy in the pool.")
    def pool_max_resp_time(self, data):
        self._pool_max_resp_time = data

    @method_switch('proxy_pool_timeout',
        group=__group__,
        default=_proxy_pool_timeout)
    def proxy_pool_timeout(self, data):
        self._proxy_pool_timeout = data

    @method_switch('pool_min_req_proxy',
        group=__group__,
        default=_pool_min_req_proxy,
        help=(
            "The minimum number of processed requests to estimate the quality "
            "of proxy (in accordance with max_error_rate and max_resp_time)"
        ))
    def pool_min_req_proxy(self, data):
        self._pool_min_req_proxy = data

    def proxy_pool_config(self, method=None):
        method = method or self._method
        return {
            'pool_min_req_proxy': self._pool_min_req_proxy[method],
            'pool_max_error_rate': self._pool_max_error_rate[method],
            'pool_max_resp_time': self._pool_max_resp_time[method],
            'proxy_pool_timeout': self._proxy_pool_timeout[method],
        }


class ProxyBrokerArgs(ConfigArgs):

    __group__ = "Proxy Broker"

    _broker_max_conn = {'GET': 50, 'POST': 200}
    _broker_max_tries = {'GET': 2, 'POST': 2}
    _broker_req_timeout = {'GET': 5, 'POST': 5}
    _broker_verify_ssl = False

    @method_switch('broker_max_conn',
        group=__group__,
        default=_broker_max_conn,
        help="The maximum number of concurrent checks of proxies.")
    def broker_max_conn(self, data):
        self._broker_max_conn = data

    @method_switch('broker_max_tries',
        group=__group__,
        default=_broker_max_tries,
        help="The maximum number of attempts to check a proxy.")
    def broker_max_tries(self, data):
        self._broker_max_tries = data

    @method_switch('broker_req_timeout',
        group=__group__,
        default=_broker_req_timeout,
        help="Timeout of a request in seconds")
    def broker_req_timeout(self, data):
        self._broker_req_timeout = data

    def proxy_broker_config(self, method=None):
        method = method or self._method
        return {
            'broker_req_timeout': self._broker_req_timeout[method],
            'broker_max_conn': self._broker_max_conn[method],
            'broker_max_tries': self._broker_max_tries[method],
            'broker_verify_ssl': self._broker_verify_ssl,
        }


class ProxyFinderArgs(ConfigArgs):

    __group__ = 'Proxy Finder'

    _proxy_countries = None
    _proxy_types = {
        'GET': ['HTTPS'],
        'POST': ['HTTPS'],
    }
    _post = {
        'GET': False,
        'POST': True,
    }

    _proxy_limit = {'GET': 50, 'POST': 200}

    @method_switch('proxy_limit',
        group=__group__,
        default=_proxy_limit,
        help="The maximum number of proxies.")
    def proxy_limit(self, data):
        self._proxy_limit = data

    def proxy_finder_config(self, method=None):
        method = method or self._method
        return {
            'proxy_limit': self._proxy_limit[method],
            'post': self._post[method],
            'proxy_countries': self._proxy_countries,
            'proxy_types': self._proxy_types[method],
        }


class ProxyArgs(ProxyPoolArgs, ProxyFinderArgs, ProxyBrokerArgs):

    def proxy_config(self, method=None):
        config = {}
        config.update(self.proxy_pool_config(method=method))
        config.update(self.proxy_broker_config(method=method))
        config.update(self.proxy_finder_config(method=method))
        return config


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