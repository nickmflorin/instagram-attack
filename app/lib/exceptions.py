from __future__ import absolute_import


class InstagramAttackException(Exception):
    """
    Base exception class for all custom exceptions.
    """

    def __init__(self, *args):
        if len(args) == 1:
            self.message = args[0]
        else:
            self.message = self.__message__

    def __str__(self):
        return self.message


class FatalException(InstagramAttackException):
    """
    Used for checks where we need to make sure something is available or operating
    properly, and if not, the system should shut down.
    """
    pass


class UserDoesNotExist(InstagramAttackException):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class ApiException(InstagramAttackException):
    pass


class ServerApiException(ApiException):
    __message__ = "Server Error"


class ClientApiException(ApiException):

    def __init__(self, *args, **kwargs):
        super(ClientApiException, self).__init__(*args)
        self.status_code = kwargs.get('status_code') or getattr(self, '__status__', None)


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


class InstagramServerApiException(InstagramApiException):
    pass


class InstagramResponseException(InstagramClientApiException):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __message__ = "Instagram Response Error"


class TokenNotInResponse(InstagramClientApiException, BadProxyException):
    """
    Thrown if we receive a response with valid cookies but the xcrsftoken
    cookie is not in the response cookies.
    """
    __message__ = "Token was not in the response cookies."


class ResultNotInResponse(InstagramClientApiException, BadProxyException):
    """
    Thrown if we receive a response when trying to login that does not raise
    a client exception but we cannot parse the JSON from the response to get
    the result.
    """
    __message__ = "The login result could not be obtained from the response."


class CookiesNotInResponse(InstagramClientApiException, BadProxyException):
    __message__ = "No Cookies in Response"


class ClientProxyConnectionError(ClientApiException, BadProxyException):
    __message__ = "Client HTTP Proxy Error"


class ClientHttpProxyError(ClientApiException, BadProxyException):
    __message__ = "Client HTTP Proxy Error"
