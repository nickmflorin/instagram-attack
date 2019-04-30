from __future__ import absolute_import

from instattack.exceptions import AppException


class ProxyException(AppException):
    pass


class NoProxyError(ProxyException):

    __message__ = 'No More Proxies in Queue'

    def __str__(self):
        return self.__message__


class ProxyPoolException(ProxyException):
    pass


class PoolNoProxyError(ProxyPoolException):
    __message__ = 'No More Proxies; Reached Limit.'

    def __str__(self):
        return self.__message__
