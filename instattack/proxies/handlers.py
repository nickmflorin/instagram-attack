import asyncio
from proxybroker import Broker

from instattack.control import Handler, Control
from instattack.lib.utils import coro_exc_wrapper

from .pool import CustomProxyPool
from .exceptions import ProxyException


class CustomBroker(Broker, Control):
    """
    Overridden to allow custom server to be used and convenience settings
    to be implemented directly from the settings module.

    Also, the proxybroker server stops the main event loop preventing multiple
    brokers from being used.  Even though the .find() method does not use the
    server, that was the original purpose of subclassing the broker and should
    be kept in mind in case we want to reimplement the .serve() functionality.
    requests).
    """
    __subname__ = 'Proxy Broker'

    def __init__(
        self,
        proxies,
        max_tries=None,
        max_conn=None,
        timeout=None,
        verify_ssl=False,
        limit=None,
        post=False,
        countries=None,
        types=None,
        **kwargs,
    ):
        self.broker_args = {
            'max_tries': max_tries,
            'max_conn': max_conn,
            'timeout': timeout,
            'verify_ssl': verify_ssl
        }
        self.find_args = {
            'limit': limit,
            'post': post,
            'countries': countries or [],
            'types': types
        }

        self.engage(**kwargs)
        super(CustomBroker, self).__init__(proxies, **self.broker_args)

    async def find(self, loop):
        await self.start_event.wait()
        async with self.starting(loop):
            return await super(CustomBroker, self).find(**self.find_args)

    def stop(self, loop, *args, **kwargs):
        """
        This has to by a synchronous method because ProxyBroker attaches signals
        to the overridden stop method.
        """
        with self.stopping(loop):
            self._proxies.put_nowait(None)
            super(CustomBroker, self).stop(*args, **kwargs)

    def increment_limit(self):
        """
        Sometimes the proxy pool might notice something wrong with the proxies
        that are being returned from the broker, and it cannot use one.  In that
        case, if we still want to have the number of proxies defined by limit in
        the pool, we have to increment the limit of the broker.

        There might be other edge case logic we have to incorporate here.
        """
        self._limit += 1


class ProxyHandler(Handler):
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
    __subname__ = 'Proxy Handler'

    def __init__(
        self,
        # Broker Arguments
        broker_req_timeout=None,
        broker_max_conn=None,
        broker_max_tries=None,
        broker_verify_ssl=None,
        # Find Arguments
        proxy_limit=None,
        post=False,
        proxy_countries=None,
        proxy_types=None,
        # Pool Arguments
        pool_min_req_proxy=None,
        pool_max_error_rate=None,
        pool_max_resp_time=None,
        # Handler Args
        proxy_pool_timeout=None,
        proxies=None,
        **kwargs,
    ):
        super(ProxyHandler, self).__init__(**kwargs)

        self._proxies = proxies or asyncio.Queue()
        self._proxy_limit = proxy_limit

        self._broker = CustomBroker(
            self._proxies,
            max_conn=broker_max_conn,
            max_tries=broker_max_tries,
            timeout=broker_req_timeout,
            verify_ssl=broker_verify_ssl,
            # Our Broker Applies These Args to .find() Manualy
            limit=proxy_limit,
            post=post,
            countries=proxy_countries,
            types=proxy_types,
            **kwargs,
        )

        self.pool = CustomProxyPool(
            self._broker,
            timeout=proxy_pool_timeout,
            min_req_proxy=pool_min_req_proxy,
            max_error_rate=pool_max_error_rate,
            max_resp_time=pool_max_resp_time,
            **kwargs,
        )

    async def run(self, loop, prepopulate=True):
        """
        When running concurrently with other tasks/handlers, we don't always
        want to shut down the proxy handler when we hit the limit, because
        the other handler might still be using those.

        Using asyncio.gather() is not really necessary since the broker kicks
        off on it's own, it also suppresses exceptions which is not desired
        behavior.
        """

        # TODO: Test the operation without prepopulation, since it sometimes
        # slows down too much when we are waiting on proxies from the finder.
        async with self.starting(loop):
            await asyncio.gather(
                self._broker.find(loop),
                self.pool.run(loop, prepopulate=prepopulate),
            )

    async def stop(self, loop, save=False, overwrite=False):
        async with self.stopping(loop):
            self._broker.stop(loop)
            # Stopping the broker will put None in the queue which should trigger
            # the pool to set _stopped = True, which is necessary to make sure that
            # it is not waiting forever.  However, this might be faster.
            await self.pool.stop(loop, save=save, overwrite=overwrite)

    async def get(self):
        if self.stopped:
            raise ProxyException('Cannot get proxy from stopped handler.')
        # Do not want to await, we want to return the couroutine?
        return await self.pool.get()

    async def save_proxies(self, overwrite=False):
        return await self.pool.save(overwrite=overwrite)
