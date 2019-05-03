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

        # Because subclasses will have the _stopped property.
        if not hasattr(self, '_stopped'):
            self._stopped = False

        if hasattr(self, '__subname__'):
            subname = self.__subname__
        elif hasattr(self, '__name__'):
            subname = self.__name__
        else:
            subname = self.__class__.__name__

        self.__name__ = f"{self.method.upper()} {subname}"
        self.log = AppLogger(self.__name__)

    def _starting(self):
        self.log.notice(f'Starting {self.__name__}')

    def _stopping(self):
        self.log.notice(f'Stopping {self.__name__}')

    def _has_stopped(self):
        self.log.debug(f'{self.__name__} Has Been Stopped')

    @contextlib.contextmanager
    def _sync_start(self, loop):
        try:
            self._starting()
            self._stopped = False
            yield
        finally:
            return

    @contextlib.asynccontextmanager
    async def _start(self, loop):
        try:
            self._starting()
            self._stopped = False
            yield
        finally:
            return

    @contextlib.asynccontextmanager
    async def _stop(self, loop):
        try:
            self._stopping()
            yield
        finally:
            self._has_stopped()
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

    @contextlib.contextmanager
    def _sync_start(self, loop):
        self._stopper = asyncio.Event()
        try:
            self._starting()
            yield
        finally:
            return

    @contextlib.asynccontextmanager
    async def _start(self, loop):
        self._stopper = asyncio.Event()
        try:
            self._starting()
            yield
        finally:
            return

    @contextlib.asynccontextmanager
    async def _stop(self, loop):
        try:
            self._stopping()
            self._stopper.set()
            yield
        finally:
            self._has_stopped()

    @property
    def _stopped(self):
        return self._stopper.is_set()
