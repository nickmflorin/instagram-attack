from __future__ import absolute_import

from proxybroker import Broker

from instattack.logger import AppLogger


__all__ = ('CustomBroker', )


class CustomBroker(Broker):
    """
    Overridden to allow custom server to be used and convenience settings
    to be implemented directly from the settings module.

    Also, the proxybroker server stops the main event loop preventing multiple
    brokers from being used.  Even though the .find() method does not use the
    server, that was the original purpose of subclassing the broker and should
    be kept in mind in case we want to reimplement the .serve() functionality.
    requests).
    """
    log = AppLogger('Custom Proxy Broker')

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
        self.log.debug('Broker Args %s' % self.broker_args)
        super(CustomBroker, self).__init__(proxies, **self.broker_args)

    def find(self):
        self.log.notice('Broker Starting to Find Proxies...')
        self.log.debug('Broker Find Args %s' % self.find_args)
        return super(CustomBroker, self).find(**self.find_args)
