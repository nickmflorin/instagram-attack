from instattack.exceptions import AppException
from .utils import (
    get_http_exception_err_no, get_http_exception_request_method, get_http_exception_status_code,
    filtered_array)


__all__ = (
    'HttpResponseError',
    'HttpRequestError',
    'HttpFileDescriptorError',
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
)


class HttpException(AppException):

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
        ))
        if self.errno and self.errno != self.status_code:
            parts += ("Err No: %s", self.errno)
        return ' '.join(parts)


class HttpRequestError(HttpException):
    pass


# We shouldn't really need this unless we are running over large numbers
# of requests... so keep for now.
class HttpFileDescriptorError(HttpRequestError):
    # We Don't Need to Worry About Type or Subtype Since This will be Inconclusive
    # and Will Not be Stored on Proxy Model
    __treatment__ = 'inconclusive'


class HttpSSLError(HttpRequestError):
    __type__ = 'ssl'
    __subtype__ = 'ssl'
    __treatment__ = 'error'


class HttpConnectionError(HttpRequestError):
    __type__ = 'connection'
    __treatment__ = 'semifatal'


class HttpTimeoutError(HttpRequestError):
    __type__ = 'timeout'
    __subtype__ = 'timeout'
    __treatment__ = 'semifatal'


class HttpClientConnectionError(HttpConnectionError):
    __subtype__ = 'client_connection'


class HttpProxyConnectionError(HttpConnectionError):
    __subtype__ = 'proxy_connection'


class HttpServerConnectionError(HttpConnectionError):
    __subtype__ = 'server_connection'


class HttpResponseError(HttpException):
    __type__ = 'response'
    __subtype__ = 'invalid_response'
    __treatment__ = 'inconclusive'


class HttpProxyAuthError(HttpResponseError):
    """
    The server understood the request but refuses to authorize it.
    [403]

    It is tough to see with aiohttp if this is being raised in raise_for_status()
    or if it is being raised as a request error, but either way we will treat
    as a request error for now.
    """
    status_code = 403
    __subtype__ = 'proxy_auth'
    __treatment__ = 'semifatal'  # Should probably be fatal down the line.


class HttpTooManyRequestsError(HttpResponseError):
    """
    [429]

    It is tough to see with aiohttp if this is being raised in raise_for_status()
    or if it is being raised as a request error, but either way we will treat
    as a request error for now.
    """
    __subtype__ = 'too_many_requests'
    __type__ = 'too_many_requests'
    __treatment__ = 'error'
    status_code = 429


class InvalidResponseJson(HttpResponseError):

    __subtype__ = 'invalid_response_json'
    __treatment__ = 'error'


class InstagramResultError(HttpResponseError):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __subtype__ = 'invalid_instagram_result'
    __treatment__ = 'semifatal'
    status_code = 200

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"[{self.status_code}]: {self.message}"
