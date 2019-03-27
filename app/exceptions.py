from __future__ import absolute_import

__all__ = (
    'UserDoesNotExist',
    'ApiException',
    'ApiClientException',
    'ApiServerException',
    'InstagramClientException',
    'InstagramServerException',
    'InvalidUserName',
    'InstagramTooManyRequests',
)


class UserDoesNotExist(Exception):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class ApiException(Exception):

    def get_message_part(self, attr):
        attr = f"{attr}_part"
        if getattr(self, attr):
            return getattr(self, attr)
        return ""

    @property
    def parts(self):
        parts = [self.get_message_part(pt) for pt in self.identify_parts]
        parts = [pt for pt in parts if pt is not None]
        return parts

    @property
    def status_code_part(self):
        if getattr(self, 'status_code'):
            return f"[{self.status_code}];"

    @property
    def message_part(self):
        if getattr(self, 'message'):
            return f"Error: {self.message}"

    @property
    def error_type_part(self):
        if getattr(self, 'error_type'):
            return f"({self.error_type})"

    def __str__(self):
        return " ".join(self.parts)


class InvalidUserName(ApiException):
    def __init__(self, username):
        message = f'The username {username} is invalid.'
        super(InvalidUserName, self).__init__(message)


class ApiRequestsException(ApiException):
    def __init__(self, method=None, endpoint=None, proxy=None):
        self.method = method
        self.endpoint = endpoint
        self.proxy = proxy

    def __str__(self):
        return f"[{self.method}]: {self.endpoint}; PROXY: {self.proxy}"


class ApiMaxRetryError(ApiRequestsException):
    pass


class ApiTimeoutException(ApiRequestsException):
    pass


class ApiBadProxyException(ApiRequestsException):
    def __str__(self):
        return f"The proxy {self.proxy} is invalid."


class ApiClientException(ApiException):

    def __init__(self, status_code=None, message=None, error_type=None):
        self.status_code = status_code
        self.message = message
        self.error_type = error_type

    @property
    def identify_parts(self):
        return [
            'status_code',
            'message',
            'error_type',
        ]


class ApiServerException(ApiException):
    def __init__(self, response):
        super(ApiClientException, self).__init__(
            f"[{response.status_code}] Server Error: {response.reason}"
        )


class InstagramClientException(ApiClientException):
    pass


class InstagramTooManyRequests(InstagramClientException):
    def __init__(self, response):
        self.status_code = 429
        self.reason = "Too many requests"
        self.response = response

    def __str__(self):
        return f"[{self.status_code}] Client Error: {self.reason} at {self.response.url}"


class InstagramServerException(ApiServerException):
    pass
