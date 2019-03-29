from __future__ import absolute_import


class UserDoesNotExist(Exception):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class ApiException(Exception):

    def __init__(self, message=None):
        self.message = message

    def get_message_part(self, attr):
        attr = f"{attr}_part"
        if getattr(self, attr):
            return getattr(self, attr)
        return ""

    @property
    def output_components(self):
        return [
            'status_code',
            'message',
            'error_type',
        ]

    @property
    def parts(self):
        parts = [self.get_message_part(pt) for pt in self.output_components]
        parts = [pt for pt in parts if pt is not None]
        return parts

    @property
    def status_code_part(self):
        if getattr(self, 'status_code', None):
            return f"[{self.status_code}];"

    @property
    def message_part(self):
        if getattr(self, 'message', None):
            return f"Error: {self.message}"

    @property
    def error_type_part(self):
        if getattr(self, 'error_type', None):
            return f"({self.error_type})"

    def __str__(self):
        return " ".join(self.parts)


class MissingTokenException(ApiException):
    def __init__(self):
        message = "The token is missing from the session!"
        super(MissingTokenException, self).__init__(message=message)


class MissingProxyException(ApiException):
    def __init__(self):
        message = "There is no proxy associated with the session!"
        super(MissingProxyException, self).__init__(message=message)


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


class ApiBadProxyException(ApiRequestsException):

    def __str__(self):
        return f"The proxy {self.proxy} is invalid."


class ApiMaxRetryError(ApiBadProxyException):
    pass


class ApiTimeoutException(ApiBadProxyException):
    pass


class ApiSSLException(ApiBadProxyException):
    pass


class ApiClientBadProxyException(ApiBadProxyException):
    """
    Base class for exceptions that are raised after a response is received
    that should inform that the proxy should be changed.
    """

    def __init__(self, status_code=None, message=None, error_type=None):
        self.status_code = status_code
        self.message = message
        self.error_type = error_type


class ApiTooManyRequestsException(ApiClientBadProxyException):

    def __init__(self, **kwargs):
        kwargs.setdefault('status_code', 429)
        super(ApiTooManyRequestsException, self).__init__(**kwargs)


class ApiClientException(ApiException):

    def __init__(self, status_code=None, message=None, error_type=None):
        self.status_code = status_code
        self.message = message
        self.error_type = error_type


class ApiServerException(ApiException):
    def __init__(self, response):
        super(ApiClientException, self).__init__(
            f"[{response.status_code}] Server Error: {response.reason}"
        )
