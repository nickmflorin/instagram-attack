from termx.library import ensure_iterable
from .exceptions import ConfigError, FieldError


def check_null_value(func):
    def wrapped(instance, key, value):
        if value is None:
            if not instance.optional:
                raise FieldError.RequiredField(key)
            else:
                return None
        return func(instance, key, value)
    return wrapped


class Field(object):
    """
    Abstract base class for all field objects.

    Provides the interface for defining methods on a field and the basic
    configuration steps for configurable fields.
    """

    def __init__(self, default, help=None, optional=False, configurable=True):

        self._default = default
        self._help = help
        self._value = default

        # Optional Has to be Accessed Externally to Determine if Missing Value
        # Allowed
        self.optional = optional
        self.configurable = configurable

    @property
    def value(self):
        return self._value

    def configure(self, key, value):
        if not self.configurable:
            raise FieldError.NonConfigurableField(key)
        value = self.validate(key, value)
        self._value = value

    def validate(self, key, value):
        raise NotImplementedError(
            "%s must implement a validation method." % self.__class__.__name__)

    def __str__(self):
        return "%s" % self.value

    def __repr__(self):
        return self.__str__()


class ConstantField(Field):

    def __init__(self, value, help=None):
        super(ConstantField, self).__init__(
            default=value,
            configurable=False,
            optional=False,
            help=help
        )


class SetField(dict, Field):

    def __init__(self, help=None, configurable=True, **fields):
        self._help = help
        self.configurable = configurable
        self.update(**fields)

    @property
    def value(self):
        # Do We Need This?
        raise NotImplementedError()

    @property
    def optional(self):
        """
        Sets, as a whole, are only optional if EVERY field in the set is
        optional, otherwise, any required fields must be specified.
        """
        return all([v.optional for k, v in self.items()])

    def __getattr__(self, key):
        """
        Allows flexible case insensitive access of set field values as either
        dictionary fields or object attributes.
        """
        return self.__getitem__(key)

    def __getitem__(self, key):
        field = super(SetField, self).__getitem__(self.__keytransform__(key))
        if isinstance(field, SetField):
            return field
        return field.value

    def __setitem__(self, key, value):
        """
        If a SetField instance is configurable, all defined fields must be
        instances of some Field object.  The individual fields themselves can
        be configurable or non-configurable.

        If a SetField instance is non-configurable, the defined fields must be
        constants that we initialize as instances of ConstantField (which are
        non configurable) for convenience.

        A non-configurable SetField instance cannot have configurable fields, so
        we will enforce that SetField instances that are not configurable have
        constant field values.
        """

        if self.configurable:
            if not isinstance(value, Field):
                raise ConfigError(
                    "Field %s must be an instance of Field, since it belongs to "
                    "a configurable SetField." % key
                )
            super(SetField, self).__setitem__(self.__keytransform__(key), value)
        else:
            if isinstance(value, Field) and not isinstance(value, ConstantField):
                raise ConfigError(
                    "Field %s must be a constant, since it belongs to "
                    "a non-configurable SetField." % key
                )
            elif isinstance(value, ConstantField):
                super(SetField, self).__setitem__(self.__keytransform__(key), value)
            else:
                value = ConstantField(value)
                super(SetField, self).__setitem__(self.__keytransform__(key), value)

    def __delitem__(self, key):
        super(SetField, self).__delitem__(self.__keytransform__(key))

    def __contains__(self, key):
        return super(SetField, self).__contains__(self.__keytransform__(key))

    def __keytransform__(self, key):
        return key.upper()

    def configure(self, *args, **kwargs):
        """
        When configuring, all values are not instances of Field but are instead
        constant values that will be overridden for each Field instance in the
        SetField already created.
        """
        data = dict(*args, **kwargs)
        for k, v in data.items():
            if k not in self:
                raise FieldError.UnexpectedSetField(k)
            self[k].configure(k, v)

    def update(self, *args, **kwargs):
        """
        Sets the fields that belong to the SetField.  This is only done once,
        on initialization.  Updating of the SetField afterwards must be done
        through the configure method.

        [x] Note:
        ---------
        The difference between the update() and configure() method is that
        update() is the traditional dict form that will be used to set the
        field objects in the dict.  The configure() method is used to set constant
        values that override the fields stored in the dict.
        """
        for k, v in dict(*args, **kwargs).items():
            if self.__keytransform__(k) in self:
                raise FieldError.FieldAlreadySet(k)
            if not isinstance(v, Field) and self.configurable:
                raise FieldError.ExpectedFieldInstance(k)
            self.__setitem__(k, v)

    def __deepcopy__(self, memo):
        """
        Required for simple_settings module.

        Since simple_settings expects dict instances to be valid parameters
        to copy.deepcopy(), we need to establish how to deepcopy ConfigDoc
        instances.

        In order to maintain custom ConfigDoc dicts with termx objects as
        values (i.e. color, style, Format, etc.) we need to establish a
        __deepcopy__ method for each sub-doc (Colors, Formats, etc.) that
        copies these objects manually.

        Non ConfigDoc instances can be copied as normal.
        """
        obj = SetField(help=self._help, configurable=self.configurable, **dict(self))
        return obj

    @check_null_value
    def validate(self, key, value):
        """
        Value passed in will be a dictionary with each key corresponding to
        a field in the set.  They should be case insensitive.

        [x] TODO:
        --------
        Maybe have a __keytransform__ method that converts them all to lowercase?
        """
        if not isinstance(value, dict):
            raise FieldError.ExpectedDict(key, value)

    def __str__(self):
        return "<SetField %s>" % dict(self)

    def __repr__(self):
        return self.__str__()


class NumericField(Field):
    """
    Abstract base class for numeric fields where a max and a min may be
    specified.
    """

    def __init__(self, default, max=None, min=None, **kwargs):
        super(NumericField, self).__init__(default, **kwargs)
        self._max = max
        self._min = min

    @check_null_value
    def validate(self, key, value):
        if self._max and value > self._max:
            raise FieldError.ExceedsMax(key, value, self._max)
        if self._min and value < self._min:
            raise FieldError.ExceedsMin(key, value, self._min)
        return value


class IntField(NumericField):

    @check_null_value
    def validate(self, key, value):
        try:
            float(value)
        except ValueError:
            raise FieldError.ExpectedType(key, value, int)
        else:
            value = int(value)
            if value != float(value):
                raise FieldError.ExpectedType(key, value, int)
            return super(IntField, self).validate(key, value)


class FloatField(NumericField):

    @check_null_value
    def validate(self, key, value):
        try:
            value = float(value)
        except ValueError:
            raise FieldError.ExpectedType(key, value, float)
        else:
            return super(IntField, self).validate(key, value)


class PositiveIntField(IntField):
    def __init__(self, *args, **kwargs):
        kwargs['min'] = 0
        super(PositiveIntField, self).__init__(*args, **kwargs)


class YearField(IntField):
    """
    [x] TODO: Make Start and End Year Based on Current Date and Current Date - 100
    """

    def __init__(self, *args, **kwargs):
        kwargs['min'] = 1980
        kwargs['max'] = 2020
        super(YearField, self).__init__(*args, **kwargs)


class PositiveFloatField(FloatField):

    def __init__(self, *args, **kwargs):
        kwargs['min'] = 0
        super(PositiveFloatField, self).__init__(*args, **kwargs)


class TypeField(Field):

    def __init__(self, default, type, help=None):
        super(TypeField, self).__init__(default, help=help)
        self.type = type

    @check_null_value
    def validate(self, key, value):
        if not isinstance(value, self.type):
            raise FieldError.ExpectedType(key, value, self.type)
        return value


class BooleanField(TypeField):
    def __init__(self, default, help=None):
        super(BooleanField, self).__init__(default, help=help, type=bool)


class DictField(TypeField):
    """
    DictField represents a configurable field where the entire field must be
    configured, vs. allowing the configuration of individual keys independent
    from one another.

    This is NOT a SetField, it does not have an update() method and when being
    configured, the entire value of the field will be set to the value supplied.

    `type` refers to the values in the dict.
    We are not currently enforcing that but can.
    """

    def __init__(self, default, help=None, type=None):
        super(DictField, self).__init__(default, help=help, type=dict)
        self.sub_type = type

    @check_null_value
    def validate(self, key, value):
        super(DictField, self).validate(key, value)
        if self.sub_type:
            types = ensure_iterable(self.sub_type, coercion=tuple, force_coerce=True)
            for k, v in self.value.items():
                if not isinstance(v, types):
                    raise FieldError.ExpectedType(k, v, ','.join(types))
        return value

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self.value)


class ListField(TypeField):

    def __init__(self, default, type=None, help=help):
        super(ListField, self).__init__(default, help=help, type=list)
        self.sub_type = type

    @check_null_value
    def validate(self, key, value):
        super(ListField, self).validate(key, value)
        if self.sub_type:
            types = ensure_iterable(self.sub_type, coercion=tuple, force_coerce=True)
            for k, v in self.value.items():
                if not isinstance(v, types):
                    raise FieldError.ExpectedType(k, v, ','.join(types))
        return value


class PriorityField(ListField):
    """
    Custom override of a ListField.
    """
    @check_null_value
    def validate(self, value):
        """
        [x] TODO:
        --------
        Validate priority fields.
        """
        return value
