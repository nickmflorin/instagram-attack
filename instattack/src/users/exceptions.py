from instattack.src.exceptions import AppException, DirDoesNotExist, PathException


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
