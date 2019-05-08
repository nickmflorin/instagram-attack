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


class ProxyException(AppException):
    pass


class NoProxyError(ProxyException):

    __message__ = 'No More Proxies'


# We don't raise this anymore because the pool just stops when it notices this.
class BrokerNoProxyError(NoProxyError):

    __message__ = 'No More Proxies in Broker'


class ProxyPoolException(ProxyException):
    pass


class PoolNoProxyError(NoProxyError):

    __message__ = 'No More Proxies in Pool'


class TokenException(AppException):
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


class ResultNotInResponse(AppException):
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


class InvalidWriteElement(AppException):
    def __init__(self, index, value):
        self.index = index
        self.value = value

    def __str__(self):
        if self.line == "":
            return f'Cannot write element at index {self.index}, it is an empty string.'
        return f"Cannot write element at index {self.index}, it is invalid: \n {self.line}"


class UsersException(AppException):
    pass


class UserException(UsersException):
    def __init__(self, username):
        self.username = username


class DirException(UsersException):

    def __init__(self, name):
        self.name = name


class DirMissing(DirException):

    def __str__(self):
        return (
            f'Directory {self.name} is missing.\n'
            f'Was the directory {self.name} accidentally deleted?'
        )


class DirExists(DirException):

    def __str__(self):
        return (
            f'Directory {self.name} already exists.\n'
        )


class UserDirException(UserException):
    pass


class UserDirMissing(UserDirException):

    def __str__(self):
        return (
            f'User directory is missing for user {self.username}.\n'
            f'Was directory for {self.username} accidentally deleted?'
        )


class UserDirExists(UserDirException):

    def __str__(self):
        return f'User directory already exists for user {self.username}.'


class UserFileException(UserException):

    def __init__(self, username, filename):
        super(UserFileException, self).__init__(username)
        self.filename = filename


class UserFileExists(UserFileException):

    def __str__(self):
        return f'File {self.filename} already exists for user {self.username}.'


class UserFileMissing(UserFileException):

    def __str__(self):
        return (
            f'File {self.filename} missing for user {self.username}.\n'
            f'Was {self.filename} accidentally deleted?'
        )


class UserDoesNotExist(UserException):
    """
    Will be used for cases where the Instagram username is invalid, but we
    are currently not using this.
    """

    def __str__(self):
        return f"The user {self.username} does not exist."
