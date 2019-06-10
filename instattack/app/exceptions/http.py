from .base import InstattackError

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


def get_http_exception_err_no(exc):
    if hasattr(exc, 'errno'):
        return exc.errno
    return None


def get_http_exception_status_code(exc):

    if hasattr(exc, 'status'):
        return exc.status
    elif hasattr(exc, 'status_code'):
        return exc.status_code
    else:
        return None


def get_http_exception_message(exc):

    message = f"{exc.__class__.__name__}"
    content = getattr(exc, 'message', None) or str(exc)
    if content:
        message += content

    if hasattr(exc, 'errno') and exc.errno is not None:
        message += f"(Err No: {exc.errno})"
    return message


class HttpException(InstattackError):

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
    def errno(self):
        errno = get_http_exception_err_no(self.exception)
        if self.status_code and errno != self.status_code:
            return errno

    def __str__(self):
        message = f"{self.__class__.__name__}({self.exception.__class__.__name__})"
        content = getattr(self.exception, 'message', None) or str(self.exception)
        if content:
            message += content
        if self.errno is not None:
            message += f"(Err No: {self.errno})"
        return message


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
    message = 'Too many open connections'
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
