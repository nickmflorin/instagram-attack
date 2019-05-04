from instattack.exceptions import AppException


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


class InvalidWriteElement(AppException):
    def __init__(self, index, value):
        self.index = index
        self.value = value

    def __str__(self):
        if self.line == "":
            return f'Cannot write element at index {self.index}, it is an empty string.'
        return f"Cannot write element at index {self.index}, it is invalid: \n {self.line}"


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
