from instattack.app.exceptions import InstattackError


class ConfigurationError(InstattackError):
    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return "%s" % self.errors

    def humanize_errors(self):
        # TODO
        pass
