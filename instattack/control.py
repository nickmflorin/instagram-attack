from __future__ import absolute_import

import contextlib
from weakref import WeakKeyDictionary

from instattack.lib.logger import AppLogger
from instattack.lib.utils import get_caller, is_async


__all__ = ('Control', 'Handler', 'Loggable', )


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


class DynamicStopper(DynamicProperty):

    def __init__(self, default):
        # Cannot create a weak reference to boolean object.
        self.data = {}
        self.default = default

    def _create_new(self, instance):
        if getattr(instance, 'stop_event', None):
            return instance.stop_event.is_set()
        else:
            return instance._stopped

    def __set__(self, instance, value):
        # We cannot use self._create_new() for defining the initial value since
        # this value will be False for objects that have a stop event (since it
        # is initially not set).  This would result in self.stopped = False,
        # which means we cannot set self.stopped = False in the starting()
        # context.
        if not self.data.get(instance):
            self.data[instance] = self.default

        if value is False:
            self.data[instance] = self._stop(instance)
        elif value is True:
            self.data[instance] = self._start(instance)
        else:
            raise ValueError('Dynamic property `stopped` must be boolean.')

    def _stop(self, instance):
        currently_stopped = self.data[instance]
        if currently_stopped:
            raise ValueError(f'Cannot stop {instance.name}, it is already stopped.')
        if getattr(instance, 'stop_event', None):
            instance.stop_event.set()
        else:
            instance._stopped = True
        return True

    def _start(self, instance):

        currently_stopped = self.data[instance]
        if not currently_stopped:
            raise ValueError(f'Cannot start {instance.name}, it is not stopped.')
        if getattr(instance, 'stop_event', None):
            instance.stop_event.clear()
        else:
            instance._stopped = False
        return False


class Loggable(object):

    name = Identifier()
    log = DynamicLogger()


class Control(Loggable):

    name = Identifier()
    stopped = DynamicStopper(False)

    def engage(self, method=None, lock=None, start_event=None, stop_event=None,
            user=None, queue=None):

        self.__method__ = method
        self._stopped = False

        self.lock = lock

        # TODO: Figure out how to incorporate the start_event into the behavior
        # of the stopped property.
        self.stop_event = stop_event
        self.start_event = start_event

        self.user = user
        self.queue = queue

    def _stopping(self):
        self.log.notice(f'Stopping {self.name}')

    def _has_stopped(self):
        self.log.debug(f'{self.name} Was Successfully Stopped')

    def starting(self, loop):
        func = get_caller(correction=2)
        is_asynchronous = is_async(func)

        @contextlib.asynccontextmanager
        async def _start():
            self.stopped = False
            try:
                self.log.notice(f'Starting {self.name}')
                yield
            except Exception as e:
                raise e
            else:
                self.log.debug(f'{self.name} Was Successfully Started')
                return

        @contextlib.contextmanager
        def _sync_start():
            self.stopped = False
            try:
                self.log.notice(f'Starting {self.name}')
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
        func = get_caller(correction=2)
        is_asynchronous = is_async(func)

        if self.stopped:
            raise ValueError(f'Cannot stop {self.name}, it is already stopped.')

        @contextlib.asynccontextmanager
        async def _stop():
            # self.stopped = True
            try:
                self.log.notice(f'Stopping {self.name}')
                yield
            except Exception as e:
                raise e
            else:
                self.log.debug(f'{self.name} Was Successfully Stopped')
                return

        @contextlib.contextmanager
        def _sync_stop():
            # self.stopped = True
            try:
                self.log.notice(f'Stopping {self.name}')
                yield
            except Exception as e:
                raise e
            else:
                self.log.debug(f'{self.name} Was Successfully Stopped')
                return

        if is_asynchronous:
            return _stop()
        return _sync_stop()


class Handler(Control):

    def __init__(self, **kwargs):
        self.engage(**kwargs)
