from __future__ import absolute_import

import contextlib
from weakref import WeakKeyDictionary

from instattack.lib import is_async_caller
from instattack.lib import AppLogger


__all__ = ('Control', 'Loggable', )


log = AppLogger(__file__)


class DynamicProperty(object):
    """
    Base class for properties that provide basic configuration and control
    variables whose value might depend on how something is initialized or
    used.
    """
    default = None

    def __init__(self):
        self.data = WeakKeyDictionary()

    def __get__(self, instance, owner):

        if not self.data.get(instance):
            self.data[instance] = self._create_new(instance)
        return self.data[instance]

    def __set__(self, instance, value):
        raise ValueError('Cannot set this dynamic property.')


class Identifier(DynamicProperty):

    def _create_new(self, instance):
        """
        Creates the value of the property that will be assigned to the given
        instance.
        """
        value = None
        if hasattr(instance, '__name__'):
            value = instance.__name__
        else:
            value = instance.__class__.__name__

        if getattr(instance, '__method__', None):
            value = f"{instance.__method__.upper()} {value}"
        return value


class DynamicLogger(DynamicProperty):

    def _create_new(self, instance):
        return AppLogger(instance.name)


class Loggable(object):

    name = Identifier()
    log = DynamicLogger()


class Control(Loggable):

    name = Identifier()

    def engage(self, method=None, lock=None, start_event=None, stop_event=None,
            user=None, queue=None):

        self.__method__ = method
        self._stopped = False
        self._started = False

        self.lock = lock

        # TODO: Figure out how to incorporate the start_event into the behavior
        # of the stopped property.
        self.stop_event = stop_event
        self.start_event = start_event

        self.user = user
        self.queue = queue

    def starting(self, loop):
        is_asynchronous = is_async_caller()

        @contextlib.asynccontextmanager
        async def _start():
            try:
                self.log.info(f'Starting {self.name}')
                yield
            except Exception as e:
                raise e
            else:
                self.log.debug(f'{self.name} Was Successfully Started')
                return

        @contextlib.contextmanager
        def _sync_start():
            try:
                self.log.info(f'Starting {self.name}')
                yield
            except Exception as e:
                raise
            else:
                self.log.debug(f'{self.name} Was Successfully Started')
                return

        if is_asynchronous:
            return _start()
        return _sync_start()

    def stopping(self, loop):
        # func = get_caller(correction=2)
        # is_asynchronous = is_async(func)
        is_asynchronous = is_async_caller()

        @contextlib.asynccontextmanager
        async def _stop():
            try:
                self.log.info(f'Stopping {self.name}')
                yield
            except Exception as e:
                raise e
            else:
                self.log.debug(f'{self.name} Was Successfully Stopped')
                return

        @contextlib.contextmanager
        def _sync_stop():
            try:
                self.log.info(f'Stopping {self.name}')
                yield
            except Exception as e:
                raise e
            else:
                self.log.debug(f'{self.name} Was Successfully Stopped')
                return

        if is_asynchronous:
            return _stop()
        return _sync_stop()
