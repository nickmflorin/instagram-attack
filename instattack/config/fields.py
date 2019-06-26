from abc import ABC, abstractmethod, abstractproperty
from datetime import datetime

from termx.library import ensure_iterable
from termx.ext.utils import string_format_tuple

from .exceptions import ConfigFieldError
from .utils import SettingsFieldDict, SettingsDict


def check_null_value(func):
    def wrapped(instance, value):
        if value is None:
            if not instance.optional:
                raise ConfigFieldError.RequiredField()
            else:
                return None
        return func(instance, value)
    return wrapped


class Field(ABC):

    @abstractproperty
    def optional(self):
        pass

    @abstractproperty
    def configurable(self):
        pass

    @abstractproperty
    def help(self):
        pass

    @abstractmethod
    def configure(self, value):
        pass

    @abstractmethod
    def _validate(self, value):
        pass

    @abstractmethod
    def __str__(self):
        pass

    def __repr__(self):
        return self.__str__()


class BaseField(object):

    def __init__(self, *args, **kwargs):
        self._help = kwargs.pop('help', None)

    @property
    def help(self):
        return self._help


class ValueField(BaseField):
    """
    Abstract base class for all field objects that are not represented by
    a collection of valus.

    Provides the interface for defining methods on a field and the basic
    configuration steps for configurable fields.
    """

    def __init__(self, default, **kwargs):
        self._optional = kwargs.pop('optional', False)
        self._configurable = kwargs.pop('configurable', True)
        super(ValueField, self).__init__(**kwargs)

        self._value = default

    @property
    def optional(self):
        return self._optional

    @property
    def configurable(self):
        return self._configurable

    def configure(self, value):
        self.value = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        if not self.configurable:
            raise ConfigFieldError.NonConfigurableField(
                ext="Configurability should be checked by container and not field itself."
            )
        val = self._validate(val)
        self._value = val

    def __str__(self):
        if isinstance(self.value, tuple):
            return "%s" % string_format_tuple(self.value)
        return "%s" % self.value


class SeriesMixin(object):

    def _validate_element_val(self, v):
        """
        [x] TODO:
        --------
        Differentiate between expected types of fields vs. values in the
        ConfigFieldError instantiations.
        """
        if isinstance(v, Field):
            raise ConfigFieldError.UnexpectedFieldInstance()

        if self._values:
            tp = self._values.get('type')
            if tp:
                types = ensure_iterable(tp, coercion=tuple, force_coerce=True)
                if not isinstance(v, types):
                    raise ConfigFieldError.ExpectedType(v, *types)

            allowed = self._values.get('allowed')
            if allowed:
                if v not in allowed:
                    raise ConfigFieldError.DisallowedValue(value=v)


class MappedMixin(SeriesMixin):

    def _validate_element_key(self, k):
        """
        [x] TODO:
        --------
        Differentiate between expected types of fields vs. values in the
        ConfigFieldError instantiations.
        """
        if self._keys:
            tp = self._keys.get('type')
            if tp:
                types = ensure_iterable(tp, coercion=tuple, force_coerce=True)
                if not isinstance(k, types):
                    raise ConfigFieldError.ExpectedType(k, *types)

            allowed = self._values.get('allowed')
            if allowed:
                if k not in allowed:
                    raise ConfigFieldError.DisallowedKey(key=k)


class SeriesField(ValueField, SeriesMixin):

    def __init__(self, default, values=None, **kwargs):
        super(SeriesField, self).__init__(default, **kwargs)

        # Validate Parameters
        self._values = values or {}

    @check_null_value
    def _validate(self, value):
        """
        We do not allow a ListField to store instances of other fields, that
        would be more appropriate for a SetField.
        """
        if not isinstance(value, list):
            raise ConfigFieldError.ExpectedType(value, list)

        for v in value:
            self._validate_element_val(v)
        return value


class MappedField(SettingsDict, MappedMixin):
    """
    Abstract base class for field instances that store collections of fields
    or other values.

    Offers attribute access and key access by case insensitive values and
    stores the collections of values in the field as a dict.
    """

    def __init__(self, default, values=None, keys=None, **kwargs):
        super(MappedField, self).__init__(**default)

        self._optional = kwargs.pop('optional', False)
        self._configurable = kwargs.pop('configurable', True)
        self._help = kwargs.pop('help', None)

        # Validate Parameters
        self._values = values or {}
        self._keys = keys or {}

    @property
    def help(self):
        return self._help

    @property
    def optional(self):
        return self._optional

    @property
    def configurable(self):
        return self._configurable

    @check_null_value
    def _validate(self, value):
        """
        We do not allow a DictField to store instances of other fields, that
        would be more appropriate for a SetField.
        """
        if not isinstance(value, dict):
            raise ConfigFieldError.ExpectedType(value, dict)

        for k, v in value.items():
            if isinstance(v, Field):
                raise ConfigFieldError.UnexpectedFieldInstance(field=k)

            if k not in self:
                raise ConfigFieldError.CannotAddField(field=k)

            self._validate_element_key(k)
            self._validate_element_val(v)
        return value

    def configure(self, *args, **kwargs):
        if not self.configurable:
            raise ConfigFieldError.NonConfigurableField()

        data = dict(*args, **kwargs)
        self._validate(data)

        for k, v in data.items():
            self[k] = v

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, dict(self))


class SetField(SettingsFieldDict):

    def __init__(self, *args, **kwargs):

        self._optional = kwargs.pop('optional', False)
        self._configurable = kwargs.pop('configurable', True)
        self._help = kwargs.pop('help', None)

        super(SetField, self).__init__(*args, **kwargs)

    @property
    def optional(self):
        """
        Sets, as a whole, are only optional if EVERY field in the set is
        optional, otherwise, any required fields must be specified.
        """
        return all([v.optional for k, v in self.items()])

    @property
    def configurable(self):
        """
        Sets, as a whole, are only configurable if ANY field in the set is
        configurable.
        """
        return all([v.configurable for k, v in self.items()])

    @check_null_value
    def _validate(self, value):
        """
        Value passed in will be a dictionary with each key corresponding to
        a field in the set.  They should be case insensitive.
        """
        if not isinstance(value, Field):
            raise ConfigFieldError.ExpectedFieldInstance()

    def __setitem__(self, key, value):
        """
        Sets the value of the SetField based on whether or not the SetField is
        configurable.

        For configurable SetFields, they can be initialized via the update()
        method and configured via the configure() method.  Non-configurable
        SetFields cannot be configured, and thus all sub-values must be
        non-configurable and set once.
        """
        if not self.configurable:
            raise ConfigFieldError.NonConfigurableField(
                ext="Configurability should be checked by container and not field itself."
            )

        self._validate(value)
        super(SetField, self).__setitem__(self.__keytransform__(key), value)

        # # Non Configurable Set Field:
        # # --------------------------
        # # (1) All sub fields must be non configurable.
        # #    - Usually instances of ConstantField, which is non-configurable by default.
        # # (2) Cannot add fields that are already present.
        # #    - This would indicate updating or configuring a non-configurable field.
        # if key in self:
        #     raise ConfigFieldError.NonConfigurableField(key)
        # elif value.configurable:
        #     raise ConfigFieldError.CannotAddConfigurableField(key)
        # else:
        #     # This Should Only be on Initial Population
        #     super(SetField, self).__setitem__(self.__keytransform__(key), value)

    def __addfields__(self, **fields):
        """
        Method that is not supposed to be used outside of the configuration of
        system settings.

        Adds fields to the SetField after it is first initialized.  The reasoning
        is that after the SetField is initialized, the only way to make changes
        is to configure it, which is not what we want to do.

        This is useful when we have to add fields that have values that depend
        on fields already initialized:

            INSTAGRAM = fields.SetField(
                URLS=fields.SetField(
                    HOME='https://www.instagram.com/',
                    LOGIN='https://www.instagram.com/accounts/login/ajax/',
                    TEST="https://postman-echo.com/post",
                    configurable=False,
                ),
            )

            HEADERS = fields.PersistentDictField({
                'Referer': INSTAGRAM.urls.home,
                "User-Agent": USERAGENT,
            })

            INSTAGRAM.__addfields__(HEADERS=HEADERES)
        """
        for k, v in fields.items():
            # DO WE EVEN NEED THIS?
            # if self.__keytransform__(k) in self:
            #     raise ConfigFieldError.FieldAlreadySet(k)

            # if not isinstance(v, Field):
            #     raise ConfigFieldError.ExpectedFieldInstance(k)

            self.__setitem__(k, v)

    def configure(self, *args, **kwargs):
        """
        Overrides the fields that belong to the SetField.  All keys must already
        belong to the SetField and all values must be non-Field instances.

        Updating the SetField requires the values to be Field instances, whereas
        configuring requires dict instances.
        """
        if not self.configurable:
            raise ConfigFieldError.NonConfigurableField(
                ext="Configurability should be checked by container and not field itself."
            )

        # TODO: Ensure value is a dict
        for k, v in dict(*args, **kwargs).items():

            # Do Not Allow Configuration w/ Fields - Only on Initialization
            if isinstance(v, Field):
                raise ConfigFieldError.UnexpectedFieldInstance(field=k)

            if k not in self:
                raise ConfigFieldError.CannotAddField(field=k)

            field = self[k]
            if not field.configurable:
                raise ConfigFieldError.NonConfigurableField(field=k)

            self[k].configure(v)

    def update(self, *args, **kwargs):
        """
        Sets the fields that belong to the SetField.  This is only done once,
        on initialization.  Updating of the SetField afterwards must be done
        through the configure method.

        Updating the SetField requires the values to be Field instances, whereas
        configuring requires dict instances.
        """
        for k, v in dict(*args, **kwargs).items():

            # Update Requires Field Instances (Initialization of SetField)
            if not isinstance(v, Field):
                raise ConfigFieldError.ExpectedFieldInstance(field=k)

            if self.__keytransform__(k) in self:
                raise ConfigFieldError.FieldAlreadySet(field=k)

            self.__setitem__(k, v)


Field.register(ValueField)
Field.register(SeriesField)
Field.register(MappedField)
Field.register(SetField)


class ConstantField(ValueField):
    """
    A constant field that is non configurable.  This will more often be used
    internally to create Field instances of system settings values that are
    not initialized as Field instances, which we treat as non-configurable
    constants by default.
    """

    def __init__(self, value, help=None):
        super(ConstantField, self).__init__(
            default=value,
            configurable=False,
            optional=False,
            help=help
        )

    def _validate(self, v):
        if isinstance(v, dict):
            raise ConfigFieldError.UnexpectedType(v, dict,
                ext='ConstantField(s) cannot be configured with dict instances.')
        return v


class DictField(MappedField):
    """
    DictField represents a configurable field where the entire field must be
    configured, vs. allowing the configuration of individual keys independent
    from one another.

    This is NOT a SetField, it does not have an update() method and when being
    configured, the entire value of the field will be set to the value supplied.
    """
    pass


class ListField(SeriesField):
    pass


class NumericField(ValueField):
    """
    Abstract base class for numeric fields where a max and a min may be
    specified.
    """

    def __init__(self, default, max=None, min=None, **kwargs):
        super(NumericField, self).__init__(default, **kwargs)
        self._max = max
        self._min = min

    @check_null_value
    def _validate(self, value):
        if self._max and value > self._max:
            raise ConfigFieldError.ExceedsMax(value=value, max=self._max)
        if self._min and value < self._min:
            raise ConfigFieldError.ExceedsMin(value=value, min=self._min)
        return value


class IntField(NumericField):

    @check_null_value
    def _validate(self, value):
        try:
            float(value)
        except ValueError:
            raise ConfigFieldError.ExpectedType(value, int)
        else:
            value = int(value)
            if value != float(value):
                raise ConfigFieldError.ExpectedType(value, int)
            return super(IntField, self).validate(value)


class FloatField(NumericField):

    @check_null_value
    def _validate(self, value):
        try:
            value = float(value)
        except ValueError:
            raise ConfigFieldError.ExpectedType(value, float)
        else:
            return super(IntField, self).validate(value)


class PositiveIntField(IntField):

    def __init__(self, *args, **kwargs):
        kwargs['min'] = 0
        super(PositiveIntField, self).__init__(*args, **kwargs)


class YearField(IntField):

    def __init__(self, *args, **kwargs):
        kwargs['max'] = datetime.today().year

        # Nobody lives past 100, and if they do they DEFINITELY don't have an
        # Instagram account.
        kwargs['min'] = kwargs['max'] - 100
        super(YearField, self).__init__(*args, **kwargs)


class PositiveFloatField(FloatField):

    def __init__(self, *args, **kwargs):
        kwargs['min'] = 0
        super(PositiveFloatField, self).__init__(*args, **kwargs)


class BooleanField(ValueField):

    @check_null_value
    def _validate(self, value):
        if not isinstance(value, bool):
            raise ConfigFieldError.ExpectedType(value, bool)
        return value


class PriorityField(ListField):
    """
    Custom override of a ListField.

    [x] TODO:
    --------
    Implement proper validation based on proxy model fields and proper
    initialization.
    """
    @check_null_value
    def _validate(self, value):
        return value
