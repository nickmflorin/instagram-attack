from .http_exceptions import *  # noqa
from .groups import *  # noqa
from .utils import get_http_exception_status_code


def get_exception_for_status_code(exc):

    STATUS_CODE_EXCEPTIONS = {
        403: HttpProxyAuthError,
        429: HttpTooManyRequestsError,
    }
    status_code = get_http_exception_status_code(exc)
    if status_code in STATUS_CODE_EXCEPTIONS:
        return STATUS_CODE_EXCEPTIONS[status_code]


def find_response_error(exc):

    if isinstance(exc, HTTP_RESPONSE_ERRORS):
        our_exc = get_exception_for_status_code(exc)
        if our_exc:
            return our_exc(exc)
        else:
            if isinstance(exc, RESPONSE_FORMAT_ERRORS):
                return InvalidResponseJson(exc)
            elif isinstance(exc, GENERAL_RESPONSE_ERRORS):
                return HttpResponseError(exc)

            # [!] IMPORTANT:
            # We're not sure if this is restricted to all 4xx errors but for now
            # it will be fine.  PROXY_CLIENT_ERRORS right now just consists
            # of ClientHttpProxyError.
            elif isinstance(exc, PROXY_CLIENT_ERRORS):
                return HttpProxyAuthError(exc)

            # Just return out own exception for CUSTOM_RESPONSE_ERRORS since
            # it does not need to be wrapped.
            elif isinstance(exc, CUSTOM_RESPONSE_ERRORS):
                return exc
            else:
                raise exc
    else:
        raise exc


def find_request_error(exc):
    """
    Classifies different HTTP request based errors that we run into into our
    classification scheme meant for determining how to handle proxies.

    Our classification scheme essentially just wraps the exceptions and groups
    them together.
    """
    if isinstance(exc, HTTP_REQUEST_ERRORS):
        our_exc = get_exception_for_status_code(exc)
        if our_exc:
            return our_exc(exc)
        else:
            if isinstance(exc, SEVER_CONNECTION_ERRORS):
                return HttpServerConnectionError(exc)

            elif isinstance(exc, PROXY_CONNECTION_ERRORS):
                return HttpProxyConnectionError(exc)

            elif isinstance(exc, CLIENT_CONNECTION_ERRORS):
                return HttpClientConnectionError(exc)

            elif isinstance(exc, SSL_ERRORS):
                return HttpSSLError(exc)

            elif isinstance(exc, TIMEOUT_ERRORS):
                return HttpTimeoutError(exc)

            else:
                raise exc
    else:
        raise exc
