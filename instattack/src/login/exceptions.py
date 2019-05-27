from instattack.exceptions import AppException


class NoPasswordsError(AppException):

    __message__ = 'There are no passwords to try.'
