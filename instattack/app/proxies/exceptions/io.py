from plumbum.path import LocalPath

from .base import AppException


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


# Not currently used only because saving attempts is done via background tasks
# that are suppressing exceptions.
class UserAttemptExists(AppException):

    def __init__(self, user, attempt):
        self.user = user
        self.attempt = attempt

    def __str__(self):
        return f"The attempt {self.attempt} already exists for user {self.user.username}."
