from instattack.src.exceptions import DirDoesNotExist, PathException


class UserDirDoesNotExist(DirDoesNotExist):
    pass


class UserFileException(PathException):

    def __init__(self, path, user):
        super(UserFileException, self).__init__(path)
        self.user = user


class UserFileDoesNotExist(UserFileException):

    def __str__(self):
        return f'The file {self.filename} does not exists for user {self.user.username}.'
