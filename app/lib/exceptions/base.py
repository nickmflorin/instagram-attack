from __future__ import absolute_import


class InstagramAttackException(Exception):
    """
    Base exception class for all custom exceptions.
    """

    def __init__(self, message):
        self.message = message
        super(InstagramAttackException, self).__init__(message)

    def __str__(self):
        return self.message


class UserDoesNotExist(InstagramAttackException):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class EngineException(InstagramAttackException):
    pass
