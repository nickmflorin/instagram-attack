from .base import InstattackError
from .utils import (
    get_http_exception_err_no, get_http_exception_request_method, get_http_exception_status_code,
    filtered_array)


__all__ = (
    'HttpResponseError',
    'HttpRequestError',
    'HttpTooManyOpenConnections',
    'HttpSSLError',
    'HttpConnectionError',
    'HttpTimeoutError',
    'HttpClientConnectionError',
    'HttpProxyConnectionError',
    'HttpProxyAuthError',
    'HttpTooManyRequestsError',
    'HttpServerConnectionError',
    'InvalidResponseJson',
    'InstagramResultError',
    'HttpProxyClientError',
)


class HttpException(InstattackError):

    __message__ = None
    __hold__ = False

    def __init__(self, exception):
        self.exception = exception

    @property
    def __treatment__(self):
        return NotImplementedError()

    @property
    def __type__(self):
        return NotImplementedError()

    @property
    def __subtype__(self):
        return NotImplementedError()

    @property
    def status_code(self):
        return get_http_exception_status_code(self.exception)

    @property
    def request_method(self):
        return get_http_exception_request_method(self.exception)

    @property
    def errno(self):
        return get_http_exception_err_no(self.exception)

    def __str__(self):
        parts = filtered_array(*(
            f"{self.__class__.__name__}({self.exception.__class__.__name__}):",
            self.request_method,
            ("[%s]", self.status_code),
            self.__message__,
        ))
        if self.errno and self.errno != self.status_code:
            parts += ("Err No: %s", self.errno)
        return ' '.join(parts)


class HttpRequestError(HttpException):
    pass


class HttpSSLError(HttpRequestError):
    __type__ = 'ssl'
    __subtype__ = 'ssl'


class HttpConnectionError(HttpRequestError):
    __type__ = 'connection'


class HttpTimeoutError(HttpRequestError):
    __type__ = 'timeout'
    __subtype__ = 'timeout'


class HttpClientConnectionError(HttpConnectionError):
    __subtype__ = 'client_connection'


class HttpProxyConnectionError(HttpConnectionError):
    __subtype__ = 'proxy_connection'


class HttpProxyClientError(HttpConnectionError):
    __subtype__ = 'proxy_client'
    __type__ = 'client'


class HttpServerConnectionError(HttpConnectionError):
    __subtype__ = 'server_connection'


class HttpResponseError(HttpException):
    __type__ = 'response'
    __subtype__ = 'invalid_response'


class HttpProxyAuthError(HttpResponseError):
    """
    The server understood the request but refuses to authorize it.
    [403]

    It is tough to see with aiohttp if this is being raised in raise_for_status()
    or if it is being raised as a request error.
    """
    status_code = 403
    __subtype__ = 'proxy_auth'
    __type__ = 'client'


class HttpTooManyOpenConnections(HttpRequestError):
    """
    [503]
    """
    __message__ = 'Too many open connections'
    __subtype__ = 'too_many_open_connections'
    __hold__ = True

    status_code = 503


class HttpTooManyRequestsError(HttpResponseError):
    """
    [429]

    It is tough to see with aiohttp if this is being raised in raise_for_status()
    or if it is being raised as a request error.
    """
    __subtype__ = 'too_many_requests'
    __hold__ = True

    status_code = 429


class InvalidResponseJson(HttpResponseError):

    __subtype__ = 'invalid_response_json'


class InstagramResultError(HttpResponseError):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __subtype__ = 'invalid_instagram_result'
    status_code = 200

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"[{self.status_code}]: {self.message}"
