from __future__ import absolute_import


class InstagramAttackException(Exception):
    """
    Base exception class for all custom exceptions.
    """
    pass


class UserDoesNotExist(InstagramAttackException):
    def __init__(self, username):
        message = "The user %s does not exist." % username
        super(UserDoesNotExist, self).__init__(message)


class EngineException(InstagramAttackException):
    pass


class ApiException(InstagramAttackException):

    def __init__(self, message=None, endpoint=None, proxy=None):
        self.message = message or getattr(self, 'message', None)
        self.endpoint = endpoint
        self.proxy = proxy

    @property
    def parts(self):
        return [
            self._message,
            self._endpoint,
            self._proxy,
        ]

    @property
    def _message(self):
        if getattr(self, 'message', None):
            return f"Error: {self.message}"

    @property
    def _endpoint(self):
        if getattr(self, 'endpoint', None):
            return f"({self.endpoint})"

    @property
    def _proxy(self):
        if getattr(self, 'proxy', None):
            return f"<{self.proxy.ip}>"

    def __str__(self):
        parts = list(filter(lambda x: x, self.parts))
        return "; ".join(parts)
