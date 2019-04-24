from __future__ import absolute_import

from instattack.exceptions import AppException


class UsersException(AppException):
    pass


class UserException(UsersException):
    def __init__(self, username):
        self.username = username


class DirException(UsersException):

    def __init__(self, name):
        self.name = name


class DirMissing(DirException):

    def __str__(self):
        return (
            f'Directory {self.name} is missing.\n'
            f'Was the directory {self.name} accidentally deleted?'
        )


class DirExists(DirException):

    def __str__(self):
        return (
            f'Directory {self.name} already exists.\n'
        )


class UserDirException(UserException):
    pass


class UserDirMissing(UserDirException):

    def __str__(self):
        return (
            f'User directory is missing for user {self.username}.\n'
            f'Was directory for {self.username} accidentally deleted?'
        )


class UserDirExists(UserDirException):

    def __str__(self):
        return f'User directory already exists for user {self.username}.'


class UserFileException(UserException):

    def __init__(self, username, filename):
        super(UserFileException, self).__init__(username)
        self.filename = filename


class UserFileExists(UserFileException):

    def __str__(self):
        return f'File {self.filename} already exists for user {self.username}.'


class UserFileMissing(UserFileException):

    def __str__(self):
        return (
            f'File {self.filename} missing for user {self.username}.\n'
            f'Was {self.filename} accidentally deleted?'
        )


class UserDoesNotExist(UserException):
    """
    Will be used for cases where the Instagram username is invalid, but we
    are currently not using this.
    """

    def __str__(self):
        return f"The user {self.username} does not exist."
