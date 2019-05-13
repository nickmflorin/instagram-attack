from __future__ import absolute_import

from weakref import WeakKeyDictionary

from instattack.logger import AppLogger


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


class LoggableMixin(object):

    name = Identifier()
    log = DynamicLogger()
