from __future__ import absolute_import

from .base import InstagramAttackException


class ApiException(InstagramAttackException):

    def __init__(self, *args, **kwargs):
        if len(args) == 1:
            self.message = args[0]
        elif kwargs.get('message'):
            self.message = kwargs['message']
        else:
            self.message = self.__message__


class ServerApiException(ApiException):
    __message__ = "Server Error"


class ClientApiException(ApiException):

    def __init__(self, message, status_code=None, **kwargs):
        super(ClientApiException, self).__init__(message, **kwargs)
        if not hasattr(self, '__status__'):
            self.status_code = status_code
        else:
            self.status_code = self.__status__


class BadProxyException(object):
    pass


class ForbiddenException(ClientApiException):

    __status__ = 403
    __message__ = "Authorization Error"


class TooManyRequestsException(ServerApiException, BadProxyException):
    __status__ = 429
    __message__ = "Too many requests"


class MaxRetryException(ServerApiException, BadProxyException):
    __message__ = "Max Number of Retries Exceeded"


class ServerTimeoutError(ServerApiException, BadProxyException):
    __message__ = "Request Timed Out"


class ClientOSError(ServerApiException, BadProxyException):
    """
    Derived from ClientOSErrorof aiohttp.
    """
    __message__ = "Proxy Connection Error"


class ServerDisconnectedError(ServerApiException, BadProxyException):
    """
    Derived from ServerDisconnectedError aiohttp.
    """
    __message__ = "Proxy Disconnect Error"


class InstagramApiException(ApiException):
    pass


class InstagramClientApiException(InstagramApiException):
    __message__ = "Instagram Client Error"

    def __init__(self, status_code=None, **kwargs):
        if not hasattr(self, '__status__'):
            self.status_code = status_code
        else:
            self.status_code = self.__status__


class InstagramServerApiException(InstagramApiException):
    pass


class InstagramResponseException(InstagramClientApiException):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __message__ = "Instagram Response Error"

    def __init__(self, result=None, **kwargs):
        self.result = result
        if 'message' not in kwargs:
            kwargs['message'] = self.result.error_message
        super(InstagramResponseException, self).__init__(**kwargs)


class TokenNotInResponse(InstagramClientApiException, BadProxyException):
    """
    Thrown if we receive a response with valid cookies but the xcrsftoken
    cookie is not in the response cookies.
    """
    __message__ = "Token was not in the response coookies."


class CookiesNotInResponse(InstagramClientApiException, BadProxyException):
    __message__ = "No Cookies in Response"


class ClientProxyConnectionError(ClientApiException, BadProxyException):
    __message__ = "Client HTTP Proxy Error"


class ClientHttpProxyError(ClientApiException, BadProxyException):
    __message__ = "Client HTTP Proxy Error"
