from .base import InstattackError
from .io import DirDoesNotExist, PathException


class UserError(InstattackError):

    __message__ = "%s"

    def __init__(self, username):
        self.username = username

    def __str__(self):
        return self.__message__ % self.username


class UserDoesNotExist(UserError):
    __message__ = "User %s does not exist."


class UserExists(UserError):
    __message__ = "User %s already exists."


class UserDirDoesNotExist(DirDoesNotExist):
    pass


class UserFileException(PathException):

    def __init__(self, path, user):
        super(UserFileException, self).__init__(path)
        self.user = user


class UserFileDoesNotExist(UserFileException):

    def __str__(self):
        return f'The file {self.filename} does not exists for user {self.user.username}.'


# Not currently used only because saving attempts is done via background tasks
# that are suppressing exceptions.
class UserAttemptExists(InstattackError):

    def __init__(self, user, attempt):
        self.user = user
        self.attempt = attempt

    def __str__(self):
        return f"The attempt {self.attempt} already exists for user {self.user.username}."
