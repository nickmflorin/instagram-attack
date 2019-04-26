from __future__ import absolute_import

import asyncio

from datetime import datetime
from urllib.parse import urlparse

import stopit

from instattack import exceptions
from instattack.conf import settings

from instattack.proxies import BROKERS
from instattack.proxies.server import CustomProxyPool
from instattack.proxies.utils import read_proxies, filter_proxies, filter_proxy
from instattack.proxies.models import Proxy

from .base import Handler


class ProxyProducerMixin(object):
    """
    Portion of ProxyHandler that is responsible for reading proxies from the
    ProxyBroker ProxyPool and puting results in the queue if they meet
    certain criteria.
    """

    async def get_from_pool(self, max_error_rate=None, max_resp_time=None):
        # Leave these optional now for flexibility - this can be useful to use
        # outside of this class.
        max_error_rate = max_error_rate or self.max_error_rate
        max_resp_time = max_resp_time or self.max_resp_time

        with stopit.SignalTimeout(self.pool_max_wait_time) as timeout_mgr:
            while True:
                proxy = await self.pool.get(scheme=self.scheme)
                if not proxy:
                    self.log.debug('Proxy Pool Returned None')
                    return proxy

                # TODO: Make it so that the pool works with our model of Proxy and
                # our model of Proxy includes additional info.
                _proxy = Proxy(
                    host=proxy.host,
                    port=proxy.port,
                    avg_resp_time=proxy.avg_resp_time,
                    error_rate=proxy.error_rate,
                    is_working=proxy.is_working,
                )

                _proxy, reason = filter_proxy(
                    _proxy,
                    max_error_rate=max_error_rate,
                    max_resp_time=max_resp_time
                )
                if not _proxy:
                    if reason == 'max_error_rate':
                        message = f'Discarding Proxy with Error Rate {_proxy.error_rate}'
                    elif reason == 'max_resp_time':
                        message = f'Discarding Proxy with Avg Resp Time {_proxy.avg_resp_time}'
                    self.log.debug(message, extra={'proxy': _proxy})
                    continue

            if timeout_mgr.state == timeout_mgr.TIMED_OUT:
                raise exceptions.InternalTimeout("Timed out waiting for a proxy from pool.")
            return _proxy

    async def produce(self, loop):
        """
        Stop event should not be needed since we can break from the cycle
        by putting None into the pool, the potential issue is that None will
        be in the queue if the Broker cannot find anymore proxies as well...

        We may run into issues with that down the line.
        """
        with self.log.start_and_done(f'Producing {self.method} Proxies'):
            while True:
                try:
                    proxy = await self.get_from_pool(
                        max_error_rate=self.max_error_rate,
                        max_resp_time=self.max_resp_time
                    )
                # Weird error from ProxyBroker that makes no sense...
                # TypeError: '<' not supported between instances of 'Proxy' and 'Proxy'
                except TypeError as e:
                    self.log.warning(e)
                else:
                    # See docstring about None value.
                    if proxy is None:
                        await self.stop()
                        break

                    await self.put(proxy, update_time=False)


class ProxyHandler(Handler, ProxyProducerMixin):
    """
    We have to run handler.broker.stop() and handler.broker.find() instead
    of having an async method on ProxyHandler like `start_server()`.  At this point,
    I'm not exactly sure why - but it was causing issues.

    TODO
    ----
    We want to eventually subclass CustomProxyPool more dynamically to use our
    Proxy model and to be able to handle the validation and retrieval logic
    of a proxy.

    Once this is done, self.proxies will not be required anymore because we can
    return directly from self.pool instead of populating results of self.pool
    in self.proxies.
    """
    __name__ = 'Proxy Handler'

    def __init__(self, method='GET', **kwargs):
        kwargs['__name__'] = f'{method} {self.__name__}'
        super(ProxyHandler, self).__init__(**kwargs)

        self.method = method

        # `broker_proxies` store the results from the CustomProxyPool queue,
        # whereas `self.proxies` stores these consumed results after they are
        # validated for certain metrics and converted to our Proxy model.
        self.proxies = asyncio.Queue()
        broker_proxies = asyncio.Queue()

        # Shoud we provide any arguments to the Pool?
        self.pool = CustomProxyPool(broker_proxies)

        # We could provide timeout here but we do that on our own.
        self.broker = self.broker_cls(
            max_conn=kwargs['max_conn'],
            max_tries=kwargs['max_tries'],
            # timeout=kwargs['pool_max_wait_time']

            # Not usually applied to broker, but we apply for our custom broker.
            limit=kwargs['limit'],
            post=kwargs['post'],
            countries=kwargs['countries'],
            types=kwargs['types'],

            # These parameters are provided to the .serve() method, which we do not
            # use, but we might be able to apply them to the pool.
            # max_error_rate and max_resp_time also provided to .serve() method,
            # but we may be able to provide to pool.
            prefer_connect=kwargs['prefer_connect'],
            http_allowed_codes=kwargs['http_allowed_codes'],
            min_req_proxy=kwargs['min_req_proxy'],
        )

    async def prepopulate(self, loop):
        """
        When initially starting, it sometimes takes awhile for the proxies with
        valid credentials to populate and kickstart the password consumer.

        Prepopulating the proxies from the designated text file can help and
        dramatically increase speeds.
        """
        with self.log.start_and_done(f'Prepopulating {self.method} Proxies'):
            proxies = read_proxies(method=self.method)
            for proxy in filter_proxies(
                proxies,
                max_error_rate=self.max_error_rate,
                max_resp_time=self.max_resp_time
            ):
                await self.put(proxy, update_time=False)

    async def get_from_queue(self):
        while True:
            proxy = await self.proxies.get()

            # Emit None to Alert Consumer to Stop Listening
            if proxy is None:
                break

            # Should we maybe check these verifications before we put the
            # proxy in the queue to begin with?
            valid = await self.validate_proxy(proxy)
            if valid:
                return proxy

    async def get(self):
        """
        TODO
        ----
        We want to eventually incorporate this type of logic into the ProxyPool
        so that we can more easily control the queue output.

        We should be looking at prioritizing proxies by `confirmed = True` where
        the time since it was last used is above a threshold (if it caused a too
        many requests error) and then look at metrics.

        import heapq

        data = [
            ((5, 1, 2), 'proxy1'),
            ((5, 2, 1), 'proxy2'),
            ((3, 1, 2), 'proxy3'),
            ((5, 1, 1), 'proxy5'),
        ]

        heapq.heapify(data)
        for item in data:
            print(item)

        We will have to re-heapify whenever we go to get a proxy (hopefully not
        too much processing) - if it is, we should limit the size of the proxy queue.

        Priority can be something like (x), (max_resp_time), (error_rate), (times used)
        x is determined if confirmed AND time since last used > x (binary)
        y is determined if not confirmed and time since last used > x (binary)

        Then we will always have prioritized by confirmed and available, not confirmed
        but ready, all those not used yet... Might not need to prioritize by times
        not used since that is guaranteed (at least should be) 0 after the first
        two priorities
        """
        with stopit.SignalTimeout(self.proxy_max_wait_time) as timeout_mgr:
            proxy = await self.get_from_queue()
            self.log.info('THE CHECK BELOW IS NOT WORKING, NO PROXY HAS TIME SINCE USED')
            if proxy:
                if proxy.time_since_used():
                    # TODO: Make this debug level once we are more comfortable
                    # with operation.
                    self.log.info('Returning Proxy %s Used %s Seconds Ago' %
                        (proxy.host, proxy.time_since_used()))

        if timeout_mgr.state == timeout_mgr.TIMED_OUT:
            raise exceptions.InternalTimeout("Timed out waiting for a valid proxy.")

        return proxy

    async def stop(self):
        with self.log.start_and_done(f'Stopping {self.method} Handler'):
            await self.pool.put(None)
            self.proxies.put_nowait(None)

            self.log.info(f'Waiting for {self.method} Server to Stop...')
            self.broker.stop()

    async def confirmed(self, proxy):
        proxy.last_used = datetime.now()
        proxy.confirmed = True
        proxy.times_used += 1
        await self.proxies.put(proxy)

    async def used(self, proxy):
        """
        When we want to keep proxy in queue because we're not sure if it is
        invalid (like when we get a Too Many Requests error) but we don't want
        to note it as `confirmed` just yet.
        """
        proxy.last_used = datetime.now()
        proxy.times_used += 1
        await self.proxies.put(proxy)

    async def validate_proxy(self, proxy):
        if not proxy.last_used:
            return True
        else:
            # TODO: Move this value to settings.
            if proxy.time_since_used() >= 10:
                return True
            else:
                await self.proxies.put(proxy)
                return False

    @property
    def broker_cls(self):
        return BROKERS[self.method]

    @property
    def scheme(self):
        return urlparse(settings.URLS[self.method]).scheme

    @property
    def stopped(self):
        return self.broker._server is None

    @property
    def running(self):
        return not self.stopped
