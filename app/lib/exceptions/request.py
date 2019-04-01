from __future__ import absolute_import

from .base import ApiException


class RequestsException(ApiException):
    def __init__(self, message=None, endpoint=None, proxy=None):
        super(RequestsException, self).__init__(
            message=message,
            endpoint=endpoint,
            proxy=proxy,
        )


class BadProxyException(RequestsException):
    message = "Invalid proxy"


class MaxRetryException(RequestsException):
    message = "Max number of retries exceeded"


class RequestsTimeoutException(BadProxyException):
    message = "Request timed out"


class RequestsConnectionException(BadProxyException):
    message = "Could not connect to the proxy"


class RequestsOSError(BadProxyException):
    """
    Derived from ClientOSErrorof aiohttp.
    """
    message = "Could not connect to the proxy"


class RequestsDisconnectError(BadProxyException):
    """
    Derived from ServerDisconnectedError aiohttp.
    """
    message = "Got disconnected from the proxy"
