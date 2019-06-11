from instattack.config import constants


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


class ConfigurationError(InstattackError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return "\n" + "\n" + self.humanize_errors(self.errors) + "\n"

    def humanize_error_list(self, error_list, prev_key=None):
        errs = []

        for err in error_list:
            if not isinstance(err, str):
                errs.extend(self.convert_errors(err, prev_key=prev_key))
            else:
                errs.append(err)
        return errs

    def convert_errors(self, error_dict, prev_key=None):
        errors = []
        prev_key = prev_key or ""

        for key, value in error_dict.items():
            if prev_key:
                new_key = f"{prev_key}.{key}"
            else:
                new_key = key

            if len(value) == 1 and type(value[0]) is str:
                errors.append((new_key, value[0]))
            else:
                errs = self.humanize_error_list(value, prev_key=new_key)
                errors.extend(errs)
        return errors

    def humanize_errors(self, errors):
        tuples = self.convert_errors(errors)

        humanized = []
        for error in tuples:

            label_formatter = constants.Colors.MED_GRAY
            formatted_attr = constants.Colors.BLACK.format(bold=True)(error[0])
            formatted_error = constants.Colors.ALT_RED.format(bold=True)(error[1].title())

            humanize = (
                f"{label_formatter('Attr')}: {formatted_attr} "
                f"{label_formatter('Error')}: {formatted_error}"
            )
            humanized.append(humanize)
        return "\n".join(humanized)
