import aiohttp
import concurrent.futures
from itertools import chain
import ssl

from .http import *  # noqa
from .http import get_http_exception_status_code


EXCEPTION_STATUS_CODES = {
    403: HttpProxyAuthError,
    429: HttpTooManyRequestsError,
    503: HttpTooManyOpenConnections,
}


def get_client_response_error(exc):
    status_code = get_http_exception_status_code(exc)
    if status_code and status_code in EXCEPTION_STATUS_CODES:
        return EXCEPTION_STATUS_CODES[status_code]
    return HttpResponseError


def get_proxy_client_error(exc):
    status_code = get_http_exception_status_code(exc)
    if status_code and status_code in EXCEPTION_STATUS_CODES:
        return EXCEPTION_STATUS_CODES[status_code]
    return HttpProxyClientError


SEVER_CONNECTION_ERRORS = {
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ServerConnectionError: HttpServerConnectionError,
    aiohttp.ServerDisconnectedError: HttpServerConnectionError,
    ConnectionResetError: HttpServerConnectionError,
    ConnectionRefusedError: HttpServerConnectionError,
}


CLIENT_CONNECTION_ERRORS = {
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ClientConnectorError: HttpClientConnectionError,
    aiohttp.ClientOSError: HttpClientConnectionError,
    aiohttp.client_exceptions.ClientConnectorError: HttpClientConnectionError,
    aiohttp.client_exceptions.ClientOSError: HttpClientConnectionError,
}

PROXY_CONNECTION_ERRORS = {
    # Not sure why we have to add some of these even though they should be
    # covered by their parents...
    aiohttp.ClientProxyConnectionError: HttpProxyConnectionError,
}

SSL_ERRORS = {
    aiohttp.ClientConnectorCertificateError: HttpSSLError,
    aiohttp.ClientConnectorSSLError: HttpSSLError,
    ssl.SSLError: HttpSSLError,  # Just for Peace of Mind
}

TIMEOUT_ERRORS = {
    TimeoutError: HttpTimeoutError,
    concurrent.futures._base.TimeoutError: HttpTimeoutError,
}

RESPONSE_FORMAT_ERRORS = {
    ValueError: InvalidResponseJson,
    aiohttp.client_exceptions.ContentTypeError: InvalidResponseJson,
    aiohttp.ContentTypeError: InvalidResponseJson,
}

PROXY_CLIENT_ERRORS = {
    aiohttp.ClientHttpProxyError: get_proxy_client_error,
}

GENERAL_RESPONSE_ERRORS = {
    aiohttp.ClientResponseError: get_client_response_error,
}

CUSTOM_RESPONSE_ERRORS = {
    InstagramResultError: InstagramResultError,
}


_HTTP_REQUEST_ERRORS = (
    SEVER_CONNECTION_ERRORS,
    CLIENT_CONNECTION_ERRORS,
    PROXY_CONNECTION_ERRORS,
    SSL_ERRORS,
    TIMEOUT_ERRORS,
)

HTTP_REQUEST_ERRORS = tuple(list(chain(*([errs.keys() for errs in _HTTP_REQUEST_ERRORS]))))

_HTTP_RESPONSE_ERRORS = (
    RESPONSE_FORMAT_ERRORS,
    GENERAL_RESPONSE_ERRORS,
    CUSTOM_RESPONSE_ERRORS,
    PROXY_CLIENT_ERRORS,
)

HTTP_RESPONSE_ERRORS = tuple(list(chain(*([errs.keys() for errs in _HTTP_RESPONSE_ERRORS]))))


def find_response_error(exc):
    for error_set in _HTTP_RESPONSE_ERRORS:
        if exc.__class__ in error_set:
            err = error_set[exc.__class__]
            if (hasattr(err, '__name__') and
                    err.__name__ in (
                        'get_client_response_error', 'get_proxy_client_error')):
                err = err(exc)
            return err(exc)


def find_request_error(exc):

    for error_set in _HTTP_REQUEST_ERRORS:
        if exc.__class__ in error_set:
            err = error_set[exc.__class__]
            if (hasattr(err, '__name__') and
                    err.__name__ in (
                        'get_client_response_error', 'get_proxy_client_error')):
                err = err(exc)

            return err(exc)


def translate_error(exc):
    """
    Classifies different HTTP request based errors that we run into into our
    classification scheme meant for determining how to handle proxies.

    Our classification scheme essentially just wraps the exceptions and groups
    them together.
    """
    err = find_response_error(exc)
    if not err:
        err = find_request_error(exc)
    return err
