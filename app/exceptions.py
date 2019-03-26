from __future__ import absolute_import

__all__ = (
    'UserDoesNotExist',
    'ApiException',
    'ApiClientException',
    'ApiServerException',
    'InstagramClientException',
    'InstagramServerException',
    'InvalidUserName',
)


class UserDoesNotExist(Exception):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class ApiException(Exception):
    pass


class InvalidUserName(ApiException):
    def __init__(self, username):
        message = f'The username {username} is invalid.'
        super(InvalidUserName, self).__init__(message)


class BadProxyError(ApiException):
    def __init__(self, proxy):
        message = "The proxy {proxy} is invalid."
        super(BadProxyError, self).__init__(message)


class ApiClientException(ApiException):
    def __init__(self, response):
        super(ApiClientException, self).__init__(
            f"[{response.status_code}] Client Error: {response.reason} at {response.url}"
        )


class ApiServerException(ApiException):
    def __init__(self, response):
        super(ApiClientException, self).__init__(
            f"[{response.status_code}] Server Error: {response.reason}"
        )


class InstagramClientException(ApiClientException):
    pass


class InstagramServerException(ApiServerException):
    pass
