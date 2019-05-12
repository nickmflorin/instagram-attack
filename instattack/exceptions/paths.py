from plumbum.path import LocalPath

from .base import AppException


def dir_str(path):
    return "%s/%s" % (path.dirname, path.name)


class PathException(AppException):

    def __init__(self, path):

        if isinstance(path, str):
            path = LocalPath(path)

        self.path = path
        self.pathname = dir_str(self.path)

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
