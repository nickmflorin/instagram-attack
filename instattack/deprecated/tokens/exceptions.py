from instattack.exceptions import AppException, ClientResponseError


class TokenNotFound(AppException):
    """
    Raised when we do not have good enough proxies or enough attempts to find
    the token within the time limit.
    """
    __message__ = "Could not find a valid token within the given time limit."


class TokenNotInResponse(ClientResponseError):
    """
    Thrown if we receive a response with valid cookies but the xcrsftoken
    cookie is not in the response cookies.
    """
    __message__ = "Token was not in the response cookies."
