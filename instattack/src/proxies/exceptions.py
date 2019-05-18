from instattack.src.exceptions import AppException


class PoolNoProxyError(AppException):

    __message__ = 'No More Proxies in Pool'
