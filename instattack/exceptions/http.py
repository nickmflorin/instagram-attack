import aiohttp
import concurrent.futures

from .base import AppException
from .utils import (
    get_exception_err_no, get_exception_request_method, get_exception_status_code,
    filtered_array)


SEVER_CONNECTION_ERRORS = (
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ServerConnectionError,
    aiohttp.ServerDisconnectedError,
    ConnectionResetError,
    ConnectionRefusedError,

)

CLIENT_CONNECTION_ERRORS = (
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ClientConnectorError,
    aiohttp.ClientOSError,
    aiohttp.client_exceptions.ClientConnectorError,
    aiohttp.client_exceptions.ClientOSError,

)

PROXY_CONNECTION_ERRORS = (
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ClientProxyConnectionError,
    aiohttp.ClientHttpProxyError,
)

SSL_ERRORS = (
    aiohttp.ClientConnectorCertificateError,
    aiohttp.ClientConnectorSSLError,

)

TIMEOUT_ERRORS = (
    TimeoutError,
    concurrent.futures._base.TimeoutError,
)

HTTP_REQUEST_ERRORS = (
    SEVER_CONNECTION_ERRORS +
    CLIENT_CONNECTION_ERRORS +
    PROXY_CONNECTION_ERRORS +
    SSL_ERRORS +
    TIMEOUT_ERRORS
)

# Used to Generalize Errors in Priority
ERROR_TYPE_CLASSIFICATION = {
    'connection': (
        'client_connection',
        'proxy_connection',
        'server_connection',
        'timeout',
    ),
    'ssl': (
        'ssl',
    ),
    'response': (
        'invalid_response',
        'too_many_requests',
    )
}


class HttpException(AppException):
    __message__ = None

    def __str__(self):
        return self.__message__ or "Unknown Error Name"

        # We might want to use the same format that we do in the logger methods
        # to format the exception method here.
        return str(self.original)


class HttpResponseError(HttpException):

    def __init__(self, response):
        self.response = response
        self.status_code = response.status

    def __str__(self):
        return f"[{self.status_code}] {self.__message__}"


class HttpRequestError(HttpException):

    def __init__(self, original=None):
        self.original = original

    @property
    def status_code(self):
        if self.original:
            return get_exception_status_code(self.original)

    @property
    def request_method(self):
        if self.original:
            return get_exception_request_method(self.original)

    @property
    def errno(self):
        if self.original:
            return get_exception_err_no(self.original)

    def __str__(self):
        parts = filtered_array(
            (self.request_method, ),
            ("[%s]", self.status_code),
            ("(Err No: %s)", self.errno),
            (self.__message__, )
        )
        return ' '.join(parts)


class ClientResponseError(HttpResponseError):

    __type__ = 'response'


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


class InvalidResponseJson(ClientResponseError):

    __subtype__ = 'invalid_response'
    __message__ = "The response JSON could not be parsed."
    __treatment__ = 'semifatal'


class InstagramResultError(ClientResponseError):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __subtype__ = 'invalid_response'
    __message__ = "Instagram Result Error"
    __treatment__ = 'semifatal'

    def __init__(self, response, message):
        super(InstagramResultError, self).__init__(response)
        self.message = message

    def __str__(self):
        message = super(InstagramResultError, self).__str__()
        return f"{message}: {self.message}"


class ClientTooManyRequests(ClientResponseError):

    __subtype__ = 'too_many_requests'
    __message__ = "Too Many Requests"
    __treatment__ = 'error'


def find_request_error(exc):

    if isinstance(exc, HTTP_REQUEST_ERRORS):

        if isinstance(exc, SEVER_CONNECTION_ERRORS):
            return HttpServerConnectionError(original=exc)

        elif isinstance(exc, PROXY_CONNECTION_ERRORS):
            return HttpProxyConnectionError(original=exc)

        elif isinstance(exc, SSL_ERRORS):
            return HttpSSLError(original=exc)

        elif isinstance(exc, TIMEOUT_ERRORS):
            return HttpTimeoutError(original=exc)

        else:
            raise RuntimeError(f'Unknown Request Error {exc.__class__}')
    else:
        raise RuntimeError(f'Unknown Request Error {exc.__class__}')
