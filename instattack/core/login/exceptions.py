from instattack.exceptions import AppException, HttpException


class ResultNotInResponse(HttpException):
    """
    Thrown if we receive a response when trying to login that does not raise
    a client exception but we cannot parse the JSON from the response to get
    the result.
    """
    __message__ = "The login result could not be obtained from the response."


class InstagramResultError(HttpException):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __message__ = "Instagram Result Error"


class NoPasswordsError(AppException):

    __message__ = 'There are no passwords to try.'
