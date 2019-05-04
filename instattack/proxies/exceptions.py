from __future__ import absolute_import

from instattack.exceptions import AppException


class ProxyException(AppException):
    pass


class NoProxyError(ProxyException):

    __message__ = 'No More Proxies'


# We don't raise this anymore because the pool just stops when it notices this.
class BrokerNoProxyError(NoProxyError):

    __message__ = 'No More Proxies in Broker'


class ProxyPoolException(ProxyException):
    pass


class PoolNoProxyError(NoProxyError):

    __message__ = 'No More Proxies in Pool'
