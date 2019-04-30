from __future__ import absolute_import

from instattack.exceptions import AppException


class ProxyException(AppException):
    pass


class NoProxyError(ProxyException):

    __message__ = 'No More Proxies'


class BrokerNoProxyError(NoProxyError):

    __message__ = 'No More Proxies in Broker'


class ProxyPoolException(ProxyException):
    pass


class PoolNoProxyError(NoProxyError):

    __message__ = 'No More Proxies in Pool'
