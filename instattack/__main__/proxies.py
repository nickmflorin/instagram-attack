#!/usr/bin/env python3
import asyncio
from plumbum import cli

from instattack.logger import log_handling

from instattack.proxies import ProxyHandler
from instattack.proxies.utils import read_proxies

from .base import BaseApplication, Instattack, ConfigArgs
from .utils import method_switch


class ProxyPoolArgs(ConfigArgs):

    __group__ = 'Proxy Pool'

    _pool_max_resp_time = {'GET': 8, 'POST': 6}
    _pool_max_error_rate = {'GET': 0.5, 'POST': 0.5}
    _proxy_queue_timeout = {'GET': 8, 'POST': 8}
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

    @method_switch('proxy_queue_timeout',
        group=__group__,
        default=_proxy_queue_timeout)
    def proxy_queue_timeout(self, data):
        self._proxy_queue_timeout = data

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
            'proxy_queue_timeout': self._proxy_queue_timeout[method],
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


class ProxyServerArgs(ConfigArgs):

    __group__ = 'Proxy Server'

    _proxy_countries = None
    _proxy_types = {
        'GET': [('HTTP', ('Anonymous', 'High')), 'HTTPS'],
        'POST': ['HTTP', 'HTTPS'],
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

    def proxy_server_config(self, method=None):
        method = method or self._method
        return {
            'proxy_limit': self._proxy_limit[method],
            'post': self._post[method],
            'proxy_countries': self._proxy_countries,
            'proxy_types': self._proxy_types[method],
        }


class ProxyArgs(ProxyPoolArgs, ProxyServerArgs, ProxyBrokerArgs):

    def proxy_config(self, method=None):
        config = {}
        config.update(self.proxy_pool_config(method=method))
        config.update(self.proxy_broker_config(method=method))
        config.update(self.proxy_server_config(method=method))
        return config


@Instattack.subcommand('proxies')
class ProxyApplication(BaseApplication, ProxyArgs):

    __group__ = 'Proxy Pool'
    _method = 'GET'

    @cli.switch("--method", cli.Set("GET", "POST", case_sensitive=False))
    def method(self, method):
        self._method = method.upper()


@ProxyApplication.subcommand('test')
class ProxyTest(ProxyApplication):
    pass


@ProxyApplication.subcommand('collect')
class ProxyCollect(ProxyApplication):

    # If show is set, the proxies will just be displayed, not saved.  Otherwise,
    # they get shown and saved.
    # show = cli.Flag("--show")

    # Only applicable if --show is False (i.e. we are saving).
    clear = cli.Flag("--clear")

    @log_handling('self')
    def main(self):
        loop = asyncio.get_event_loop()

        proxies = asyncio.Queue()
        config = self.proxy_config(method=self._method)
        proxy_handler = ProxyHandler(method=self._method, proxies=proxies, **config)

        loop.run_until_complete(asyncio.gather(
            proxy_handler.produce(loop, progress=True, display=True),
            proxy_handler.broker.find()
        ))

        loop.run_until_complete(proxy_handler.save(overwrite=self.clear))

    @property
    def current_proxies(self):
        """
        TODO: We don't really need this anymore, since we are doing the saving
        in the proxy handler itself, but in the proxy handler itself it has no
        way of guaranteeing that it finds the number of proxies we want that are
        not already found, which might lead to values being less than the limit.
        """
        if self._current_proxies is None:
            if self.clear:
                self._current_proxies = []
            else:
                self._current_proxies = read_proxies(method=self._method)
                self.log.notice(f'Currently {len(self._current_proxies)} Proxies Saved.')
        return self._current_proxies
