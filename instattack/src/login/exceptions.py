from instattack.src.exceptions import AppException, ClientResponseError


class InvalidResponseJson(ClientResponseError):

    __message__ = "The response JSON could not be parsed."


class InstagramResultError(ClientResponseError):
    """
    Used when we have received a valid response that we can get JSON from but
    the response data indicates that there was an error.
    """
    __message__ = "Instagram Result Error"


class ClientTooManyRequests(ClientResponseError):

    __message__ = "Too Many Requests"


class NoPasswordsError(AppException):

    __message__ = 'There are no passwords to try.'
