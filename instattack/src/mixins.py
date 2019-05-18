from urllib.parse import urlparse
from weakref import WeakKeyDictionary

from instattack import logger
from instattack.conf import settings


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
        return logger.get_sync(instance.name)


class DynamicAsyncLogger(DynamicProperty):

    def _create_new(self, instance):
        return logger.get_async(instance.name)


class LoggableMixin(object):

    name = Identifier()
    log_sync = DynamicLogger()
    log_async = DynamicAsyncLogger()


class ModelMixin(LoggableMixin):

    @classmethod
    def count_all(cls):
        """
        Do not ask me why the count() method returns a CountQuery that does
        not have an easily accessible integer value.
        """
        return cls.all().count().__sizeof__()


class HandlerMixin(LoggableMixin):

    def engage(self, lock=None, start_event=None, stop_event=None,
            user=None, queue=None):

        self._stopped = False
        self.lock = lock

        self.stop_event = stop_event
        self.start_event = start_event
        self.user = user

    def issue_start_event(self, reason=None):
        """
        Assumes caller is an async function.

        TODO:  Is there an easy way to determine whether or not the caller is
        async or sync?
        """
        if self.start_event.is_set():
            raise RuntimeError('Start event already set.')

        self.log_async.info('Setting Start Event', extra={'other': reason})
        self.start_event.set()


class MethodHandlerMixin(HandlerMixin):

    def engage(self, method=None, **kwargs):
        if method:
            self.__method__ = method
        if not self.__method__:
            raise RuntimeError(
                'Extensions of MethodHandlerMixin must initialize with '
                'a method or have it set as a constant class attribute.'
            )
        super(MethodHandlerMixin, self).engage(**kwargs)

    @property
    def scheme(self):
        scheme = urlparse(settings.URLS[self.__method__]).scheme
        return scheme.upper()
