from instattack.exceptions import AppException


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
