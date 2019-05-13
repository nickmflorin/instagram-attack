from plumbum.path import LocalPath


class AppException(Exception):
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


class ArgumentError(AppException):
    pass


class InternalTimeout(AppException):
    """
    Thrown when we have internal logic that might wait on a result over a series
    of attempts and we want to limit the number of attempts or total time
    just in case something is wrong.
    """

    def __init__(self, seconds, reason):
        self.seconds = seconds
        self.reason = reason

    def __str__(self):
        return 'Timed out after %s seconds; Waiting: %s' % (self.seconds, self.reason)


class NoPasswordsError(AppException):

    __message__ = 'There are no passwords to try.'


class HttpException(AppException):
    pass


class ProxyException(HttpException):
    pass


# # We don't raise this anymore because the pool just stops when it notices this.
# class BrokerNoProxyError(ProxyException):

#     __message__ = 'No More Proxies in Broker'


class PoolNoProxyError(ProxyException):

    __message__ = 'No More Proxies in Pool'


class TokenException(HttpException):
    pass


class TokenNotFound(TokenException):
    """
    Raised when we do not have good enough proxies or enough attempts to find
    the token within the time limit.
    """
    __message__ = "Could not find a valid token within the given time limit."


class TokenNotInResponse(TokenException):
    """
    Thrown if we receive a response with valid cookies but the xcrsftoken
    cookie is not in the response cookies.
    """
    __message__ = "Token was not in the response cookies."


class ResultNotInResponse(HttpException):
    """
    Thrown if we receive a response when trying to login that does not raise
    a client exception but we cannot parse the JSON from the response to get
    the result.
    """
    __message__ = "The login result could not be obtained from the response."


class InstagramApiException(AppException):
    pass


class InstagramClientApiException(InstagramApiException):
    __message__ = "Instagram Client Error"


class InstagramResultError(InstagramClientApiException):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __message__ = "Instagram Result Error"


class InvalidFileLine(AppException):
    def __init__(self, index, line, reason=None):
        self.index = index
        self.line = line
        self.reason = reason

    def __str__(self):
        if self.line == "":
            return f'Line {self.index} was an empty string.'
        elif self.reason:
            return f"Line at index {self.index} is invalid: {self.reason} \n {self.line}"
        return f"Line at index {self.index} is invalid: \n {self.line}"


class PathException(AppException):

    def __init__(self, path):

        if isinstance(path, str):
            path = LocalPath(path)

        self.path = path
        self.pathname = "%s/%s" % (self.path.dirname, self.path.name)

        self.filename = None
        if self.path.is_file():
            self.filename = self.pathname.name


class DirDoesNotExist(PathException):

    def __str__(self):
        return f'The directory {self.pathname} is missing, was it accidentally deleted?'


class UserDirDoesNotExist(DirDoesNotExist):
    pass


class UserFileException(PathException):

    def __init__(self, path, user):
        super(UserFileException, self).__init__(path)
        self.user = user


class UserFileDoesNotExist(UserFileException):

    def __str__(self):
        return f'The file {self.filename} does not exists for user {self.user.username}.'
