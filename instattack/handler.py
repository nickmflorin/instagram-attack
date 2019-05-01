from __future__ import absolute_import

import asyncio
import contextlib

from instattack import AppLogger


# TODO: There has to be a cleaner way to handle the _stopped.

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

    @contextlib.asynccontextmanager
    async def _start(self, loop):
        try:
            self.log.info(f'Starting {self.__name__}')
            self._stopped = False
            yield
        finally:
            self.log.debug(f'Finished {self.__name__}')

    @contextlib.asynccontextmanager
    async def _stop(self, loop):
        try:
            self.log.info(f'Stopping {self.__name__}')
            yield
        finally:
            self._stopped = True
            self.log.debug(f'Stopped {self.__name__}')


class Handler(MethodObj):

    def __init__(self, method=None):
        self._stopper = asyncio.Event()

        if method:
            self._setup(method=method)
        else:
            self.method = None
            self.__name__ = getattr(self, '__name__', self.__class__.__name__)
            self.log = AppLogger(self.__name__)

    @contextlib.asynccontextmanager
    async def _start(self, loop):
        try:
            self.log.info(f'Starting {self.__name__}')
            self._stopper = asyncio.Event()
            yield
        finally:
            self.log.debug(f'Finished {self.__name__}')

    @contextlib.asynccontextmanager
    async def _stop(self, loop):
        try:
            self.log.info(f'Stopping {self.__name__}')
            self._stopper.set()
            yield
        finally:
            self.log.debug(f'Stopped {self.__name__}')

    @property
    def _stopped(self):
        return self._stopper.is_set()
