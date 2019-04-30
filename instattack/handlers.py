from __future__ import absolute_import

from instattack.logger import AppLogger


class MethodObj(object):

    def __init__(self, method=None):
        self._setup(method=method)

    def _setup(self, method=None):
        self.method = method or getattr(self, '__method__', None)

        if hasattr(self, '__subname__'):
            subname = self.__subname__
        elif hasattr(self, '__name__'):
            subname = self.__name__
        else:
            subname = self.__class__.__name__

        self.__name__ = f"{self.method.upper()} {subname}"
        self.log = AppLogger(self.__name__)


class Handler(MethodObj):

    def __init__(self, method=None):
        if method:
            self._setup(method=method)
        else:
            self.method = None
            self.__name__ = getattr(self, '__name__', self.__class__.__name__)
            self.log = AppLogger(self.__name__)
