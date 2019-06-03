from plumbum.path import LocalPath

from .base import InstattackError


class PathException(InstattackError):

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


class DirExists(PathException):

    def __str__(self):
        return f'The directory {self.pathname} already exists.'
