from instattack.exceptions import HttpException


class ProxyException(HttpException):
    pass


class PoolNoProxyError(ProxyException):

    __message__ = 'No More Proxies in Pool'
