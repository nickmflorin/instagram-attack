class InstattackError(Exception):

    def __init__(self, *args):
        if len(args) == 1:
            self.message = args[0]
        else:
            self.message = self.__message__

    def __str__(self):
        return self.message


class ArgumentError(InstattackError):
    pass


class ConfigurationError(InstattackError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return "%s" % self.errors

    def humanize_errors(self):
        # TODO
        pass


class InternalTimeout(InstattackError):
    """
    Thrown when we have internal logic that might wait on a result over a series
    of attempts and we want to limit the number of attempts or total time
    just in case something is wrong.
    """

    def __init__(self, seconds, reason):
        self.seconds = seconds
        self.reason = reason

    def __str__(self):
        return 'Timed out after %s seconds; Waiting: %s' % (self.seconds, self.reason)


class NoPasswordsError(InstattackError):

    __message__ = 'There are no passwords to try.'


class PoolNoProxyError(InstattackError):

    __message__ = 'No More Proxies in Pool'
