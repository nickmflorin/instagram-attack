from __future__ import absolute_import

from proxybroker import Broker

from instattack.handlers import MethodObj


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
        self.log.notice(f'{self.__name__} Starting to Find Proxies...')
        return super(CustomBroker, self).find(**self.find_args)
