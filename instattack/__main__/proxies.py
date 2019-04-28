#!/usr/bin/env python3
import asyncio
from plumbum import cli

from instattack.logger import log_handling

from instattack.proxies.utils import read_proxies, write_proxies

from instattack.utils import bar

from instattack.handlers import ProxyHandler

from .base import BaseApplication, Instattack, ConfigArgs
from .utils import method_switch


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


class ProxyBrokerArgs(ConfigArgs):

    __group__ = "Proxy Broker"

    _broker_max_conn = None
    _broker_max_tries = None
    _broker_req_timeout = None
    _broker_verify_ssl = False

    @method_switch('broker_max_conn',
        group=__group__,
        default={'GET': 50, 'POST': 200},
        help="The maximum number of concurrent checks of proxies.")
    def broker_max_conn(self, data):
        self._conditional_set('broker_max_conn', data, '_method')

    @method_switch('broker_max_tries',
        group=__group__,
        default={'GET': 2, 'POST': 2},
        help="The maximum number of attempts to check a proxy.")
    def broker_max_tries(self, data):
        self._conditional_set('broker_max_tries', data, '_method')

    @method_switch('broker_req_timeout',
        group=__group__,
        default={'GET': 5, 'POST': 5},
        help="Timeout of a request in seconds")
    def broker_req_timeout(self, data):
        self._conditional_set('broker_req_timeout', data, '_method')


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

    @method_switch('proxy_limit',
        group=__group__,
        default={'GET': 50, 'POST': 200},
        help="The maximum number of proxies.")
    def proxy_limit(self, data):
        self._conditional_set('proxy_limit', data, '_method')

    @method_switch('min_req_proxy',
        group=__group__,
        default={'GET': 5, 'POST': 3},
        help=(
            "The minimum number of processed requests to estimate the quality "
            "of proxy (in accordance with max_error_rate and max_resp_time)"
        ))
    def min_req_proxy(self, data):
        self._conditional_set('min_req_proxy', data, '_method')


class ProxyArgs(ProxyPoolArgs, ProxyServerArgs, ProxyBrokerArgs):

    def proxy_handler_config(self, method):
        return {
            # Request Args
            'broker_req_timeout': self._broker_req_timeout[method],
            'broker_max_conn': self._broker_max_conn[method],
            'broker_max_tries': self._broker_max_tries[method],
            'broker_verify_ssl': self._broker_verify_ssl,
            # Find Args
            'proxy_limit': self._proxy_limit[method],
            'post': self._post[method],
            'proxy_countries': self._proxy_countries[method],
            'proxy_types': self._proxy_types[method],
            # Pool Arguments
            'min_req_proxy': self._min_req_proxy[method],
            'max_error_rate': self._max_error_rate[method],
            'max_resp_time': self._max_resp_time[method],
            'queue_timeout': self._proxy_queue_timeout[method],
            'pool_timeout': self._proxy_pool_timeout[method],
        }


@Instattack.subcommand('proxies')
class ProxyApplication(BaseApplication, ProxyArgs):

    _current_proxies = None
    _progress = None

    # TODO: We need this to coincide with the limit from the proxy config.
    limit = cli.SwitchAttr("--limit", int, default=10)

    __group__ = 'Proxy Pool'

    @property
    def progress(self):
        if not self._progress:
            self._progress = bar(label='Collecting Proxies', max_value=self.limit)
        return self._progress

    def display_proxy(self, proxy):
        self.log.notice('Proxy, Error Rate: %s, Avg Resp Time: %s' % (
            proxy.error_rate, proxy.avg_resp_time
        ))

    def collect(self, proxies):
        loop = asyncio.get_event_loop()

        config = self.proxy_handler_config(self._method).copy()
        config['proxy_limit'] = self.limit
        proxy_handler = ProxyHandler(method=self._method, proxies=proxies, **config)

        loop.run_until_complete(asyncio.gather(
            proxy_handler.produce(loop),
            self.collect_proxies_from_pool(loop, proxy_handler),
            proxy_handler.broker.find()
        ))

    async def collect_proxies_from_pool(self, loop, proxy_handler):
        """
        This needs to work for the collect case, where we only want unique
        proxies (as long as --clear is not set) and the test case, where we
        do not care if they are unique.
        """
        # self.progress.start()

        # TODO: We probably don't need to provide these arguments anymore
        # since we should be initiallizing the broker with them.
        async for proxy in proxy_handler.get_from_pool(
            max_error_rate=self._max_error_rate[self._method],
            max_resp_time=self._max_resp_time[self._method],
        ):
            await self.handle_found_proxy(proxy)

        # Proxy Handler Should Stop On its Own
        self.log.warning('Have to figure out why the count here does not always equal the limit.')
        self.log.critical(proxy_handler.proxies.qsize())


@ProxyApplication.subcommand('test')
class ProxyTest(ProxyApplication):

    _current_proxies = []


@ProxyApplication.subcommand('collect')
class ProxyCollect(ProxyApplication):

    # If show is set, the proxies will just be displayed, not saved.  Otherwise,
    # they get shown and saved.
    show = cli.Flag("--show")

    # Only applicable if --show is False (i.e. we are saving).
    clear = cli.Flag("--clear")

    @log_handling('self')
    def main(self):
        proxies = asyncio.Queue()
        self.collect(proxies)
        if not self.show:
            self.save(proxies)

    @property
    def current_proxies(self):
        if self._current_proxies is None:
            if self.clear:
                self._current_proxies = []
            else:
                self._current_proxies = read_proxies(method=self._method)
                self.log.notice(f'Currently {len(self._current_proxies)} Proxies Saved.')
        return self._current_proxies

    async def handle_found_proxy(self, proxy):
        if proxy not in self.current_proxies:
            self.display_proxy(proxy)
            self.collected.append(proxy)
            # self.progress.update()
        else:
            self.log.warning('Discarding Proxy - Already Saved', extra={'proxy': proxy})

    def save(self):
        self.log.notice(f'Saving {len(self.collected)} Proxies to {self._method.lower()}.txt.')
        write_proxies(self._method, self.collected, overwrite=self.clear)
