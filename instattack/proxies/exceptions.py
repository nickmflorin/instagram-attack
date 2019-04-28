from __future__ import absolute_import

from instattack.exceptions import AppException


class ProxyException(AppException):
    pass


class ProxyPoolException(ProxyException):
    pass


class NoProxyError(ProxyPoolException):
    __message__ = 'No More Proxies; Reached Limit.'

    def __str__(self):
        return self.__message__


class InvalidFileLine(ProxyException):
    def __init__(self, line):
        self.line = line

    def __str__(self):
        return f"The following line is invalid: \n {self.line}"
