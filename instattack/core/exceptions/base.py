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


class ProxyMaxTimeoutError(InstattackError):

    def __init__(self, err, timeout):
        self.err = err
        self.timeout = timeout

    def __str__(self):
        return (
            f"The proxy timeout for {self.err} has been incremented to "
            f"{self.timeout}, past it's max allowed value."
        )


class ProxyPoolError(InstattackError):
    pass


class PoolNoProxyError(ProxyPoolError):

    __message__ = 'No More Proxies in Pool'


class TokenNotFound(InstattackError):

    __message__ = "Could not find a token from the response."


class ConfigError(InstattackError):
    pass


class QueueEmpty(InstattackError):

    def __init__(self, queue):
        self.queue = queue

    def __str__(self):
        return f"The queue {self.queue.__NAME__} is empty."
