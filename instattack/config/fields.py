from datetime import datetime

from termx.library import ensure_iterable
from termx.ext.utils import string_format_tuple

from .exceptions import ConfigFieldError, FieldValidationError


def check_null_value(func):
    def wrapped(instance, key, value):
        if value is None:
            if not instance.optional:
                raise ConfigFieldError.RequiredField(key)
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
            raise ConfigFieldError.NonConfigurableField(key)
        value = self.validate(key, value)
        self._value = value

    def validate(self, key, value):
        raise NotImplementedError(
            "%s must implement a validation method." % self.__class__.__name__)

    def __str__(self):
        if isinstance(self.value, tuple):
            return "%s" % string_format_tuple(self.value)
        return "%s" % self.value

    def __repr__(self):
        return self.__str__()


class ConstantField(Field):
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


class SetField(dict, Field):

    def __init__(self, help=None, configurable=True, **fields):
        self._help = help
        self.configurable = configurable
        self.update(**fields)

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

    def get(self, key):
        try:
            self.__getitem__(key)
        except KeyError:
            return None

    def __getitem__(self, key):
        field = super(SetField, self).__getitem__(self.__keytransform__(key))
        if isinstance(field, SetField):
            return field
        return field.value

    def __setitem__(self, key, value):
        """
        Sets the value of the SetField based on whether or not the SetField is
        configurable.

        For configurable SetFields, they can be initialized via the update()
        method and configured via the configure() method.  Non-configurable
        SetFields cannot be configured, and thus all sub-values must be
        non-configurable and set once.
        """

        # Even for Constants - Must always be Field instance, ConstantField will
        # be initialized on update() method.
        assert isinstance(value, Field)

        if self.configurable:
            super(SetField, self).__setitem__(self.__keytransform__(key), value)
            return

        # Non Configurable Set Field:
        # --------------------------
        # (1) All sub fields must be non configurable.
        #    - Usually instances of ConstantField, which is non-configurable by default.
        # (2) Cannot add fields that are already present.
        #    - This would indicate updating or configuring a non-configurable field.
        if key in self:
            raise ConfigFieldError.NonConfigurableField(key)
        elif value.configurable:
            raise ConfigFieldError.CannotAddConfigurableField(key)
        else:
            # This Should Only be on Initial Population
            super(SetField, self).__setitem__(self.__keytransform__(key), value)

    def __delitem__(self, key):
        super(SetField, self).__delitem__(self.__keytransform__(key))

    def __contains__(self, key):
        return super(SetField, self).__contains__(self.__keytransform__(key))

    def __keytransform__(self, key):
        return key.upper()

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

            INSTAGRAM.__adfields__(HEADERS=HEADERES)
        """
        for k, v in fields.items():
            if self.__keytransform__(k) in self:
                raise ConfigFieldError.FieldAlreadySet(k)

            # There is No Reason to Add Constants After the Fact
            if not isinstance(v, Field):
                raise ConfigFieldError.ExpectedFieldInstance(k)

            self.__setitem__(k, v)

    def configure(self, key, *args, **kwargs):
        """
        When configuring, all values are not instances of Field but are instead
        constant values that will be overridden for each Field instance in the
        SetField already created.
        """
        data = dict(*args, **kwargs)
        for k, v in data.items():
            if k not in self:
                raise ConfigFieldError.CannotAddField(k)

            if isinstance(self[k], Field):
                if isinstance(self[k], SetField):

                    # Only reason we have to check this here vs. in the field is
                    # because we provide the values as **v.
                    if not isinstance(v, dict):
                        raise FieldValidationError.ExpectedDict(v,
                            ext='SetField(s) must be configured with dict instance.')

                    self[k].configure(**v)
                else:
                    self[k].configure(k, v)
            else:
                # Constant Fields Not Configurable
                raise ConfigFieldError.NonConfigurableField(k)

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
                raise ConfigFieldError.FieldAlreadySet(k)

            # If Not a Field Instead, Assume Constant Non Configurable Field
            if not isinstance(v, Field):
                v = ConstantField(v)

            self.__setitem__(k, v)

    @check_null_value
    def validate(self, key, value):
        """
        Value passed in will be a dictionary with each key corresponding to
        a field in the set.  They should be case insensitive.
        """
        if not isinstance(value, dict):
            raise FieldValidationError.ExpectedDict(key, value)

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
            raise FieldValidationError.ExceedsMax(key, value, self._max)
        if self._min and value < self._min:
            raise FieldValidationError.ExceedsMin(key, value, self._min)
        return value


class IntField(NumericField):

    @check_null_value
    def validate(self, key, value):
        try:
            float(value)
        except ValueError:
            raise FieldValidationError.ExpectedType(key, value, int)
        else:
            value = int(value)
            if value != float(value):
                raise FieldValidationError.ExpectedType(key, value, int)
            return super(IntField, self).validate(key, value)


class FloatField(NumericField):

    @check_null_value
    def validate(self, key, value):
        try:
            value = float(value)
        except ValueError:
            raise FieldValidationError.ExpectedType(key, value, float)
        else:
            return super(IntField, self).validate(key, value)


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


class TypeField(Field):

    def __init__(self, default, type, help=None):
        super(TypeField, self).__init__(default, help=help)
        self.type = type

    @check_null_value
    def validate(self, key, value):
        if not isinstance(value, self.type):
            raise FieldValidationError.ExpectedType(key, value, self.type)
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

    [x] TODO:
    --------
    Add validation rules for type of keys but more importantly type of values
    in the dict.
    """

    def __init__(self, default, help=None, type=None, keys=None, values=None):
        super(DictField, self).__init__(default, help=help, type=dict)

        self._keys = keys or {}
        self._values = values or {}

    def _validate_key(self, k):
        if self._keys:
            tp = self._keys.get('type')
            if tp:
                types = ensure_iterable(tp, coercion=tuple, force_coerce=True)
                if not isinstance(k, types):
                    raise FieldValidationError.ExpectedKeyType(k, ','.join(types))

    def _validate_val(k, v):
        pass

    @check_null_value
    def validate(self, key, value):
        super(DictField, self).validate(key, value)
        for k, v in self.value.items():
            self._validate_key(k)
            self._validate_val(k, v)

        if self.sub_type:
            types = ensure_iterable(self.sub_type, coercion=tuple, force_coerce=True)
            for k, v in self.value.items():
                if not isinstance(v, types):
                    raise FieldValidationError.ExpectedType(k, v, ','.join(types))
        return value

    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, self.value)


class PersistentDictField(DictField):
    pass


class ListField(TypeField):
    """
    [x] TODO:
    --------
    Add better validation rules for the types of elements in the list.
    """

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
                    raise FieldValidationError.ExpectedType(k, v, ','.join(types))
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
    def validate(self, value):
        return value
