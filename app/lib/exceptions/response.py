from __future__ import absolute_import

from .base import ApiException
from .request import BadProxyException


class ClientResponseException(ApiException):

    def __init__(self, status_code=None, **kwargs):
        super(ClientResponseException, self).__init__(**kwargs)
        self.status_code = status_code or getattr(self, 'status_code', None)

    @property
    def parts(self):
        return [
            self._status_code,
            self._message,
            self._endpoint,
            self._proxy,
        ]

    @property
    def _status_code(self):
        if getattr(self, 'status_code', None):
            return f"[{self.status_code}];"


class InstagramResponseException(ClientResponseException):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    message = "Instagram response error"

    def __init__(self, error_type=None, **kwargs):
        super(InstagramResponseException, self).__init__(**kwargs)
        self.error_type = error_type

    @property
    def parts(self):
        return [
            self._status_code,
            self._message,
            self._error_type,
            self._endpoint,
            self._proxy,
        ]

    @property
    def _error_type(self):
        if getattr(self, 'error_type', None):
            return f"({self.error_type})"


class ClientBadProxyException(ClientResponseException, BadProxyException):
    """
    Base class for exceptions that are raised after a response is received
    that should inform that the proxy should be changed.
    """
    message = "Invalid proxy"

    def __init__(self, proxy=None, **kwargs):
        ClientResponseException.__init__(self, **kwargs)
        self.proxy = proxy


class TokenNotInResponse(ClientBadProxyException):
    """
    Thrown if we receive a response with valid cookies but the xcrsftoken
    cookie is not in the response cookies.
    """

    def __str__(self):
        return f"Token was not in the response coookies for proxy {self._proxy}."


class TooManyRequestsException(ClientBadProxyException):
    status_code = 429


class ClientHttpProxyException(ClientBadProxyException):
    pass


class ServerResponseException(ClientResponseException):

    def __str__(self):
        return f"{self._status_code} Server Error: {self._message}"
