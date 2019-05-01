from __future__ import absolute_import

from proxybroker import Broker

from instattack import MethodObj


__all__ = ('CustomBroker', )


class CustomBroker(Broker, MethodObj):
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
        method=None,
        max_tries=None,
        max_conn=None,
        timeout=None,
        verify_ssl=False,
        limit=None,
        post=False,
        countries=None,
        types=None
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

        self._setup(method=method)
        super(CustomBroker, self).__init__(proxies, **self.broker_args)

    def start(self, loop):
        with self._sync_start(loop):
            super(CustomBroker, self).find(**self.find_args)

    def increment_limit(self):
        """
        Sometimes the proxy pool might notice something wrong with the proxies
        that are being returned from the broker, and it cannot use one.  In that
        case, if we still want to have the number of proxies defined by limit in
        the pool, we have to increment the limit of the broker.

        There might be other edge case logic we have to incorporate here.
        """
        self._limit += 1
