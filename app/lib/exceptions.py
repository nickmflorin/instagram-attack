from __future__ import absolute_import


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


class FatalException(AppException):
    """
    Used for checks where we need to make sure something is available or operating
    properly, and if not, the system should shut down.
    """
    pass


class UserDoesNotExist(AppException):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class ApiException(AppException):
    pass


class InstagramApiException(ApiException):
    pass


class InstagramClientApiException(InstagramApiException):
    __message__ = "Instagram Client Error"


class InstagramResultError(InstagramClientApiException):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __message__ = "Instagram Result Error"


class TokenNotInResponse(InstagramClientApiException):
    """
    Thrown if we receive a response with valid cookies but the xcrsftoken
    cookie is not in the response cookies.
    """
    __message__ = "Token was not in the response cookies."


class ResultNotInResponse(InstagramClientApiException):
    """
    Thrown if we receive a response when trying to login that does not raise
    a client exception but we cannot parse the JSON from the response to get
    the result.
    """
    __message__ = "The login result could not be obtained from the response."
