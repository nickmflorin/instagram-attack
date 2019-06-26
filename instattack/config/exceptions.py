import re
from termx.ext.utils import humanize_list, ConditionalString

from instattack.core.exceptions import InstattackError


class ConfigError(InstattackError):
    pass


class FieldErrorMeta(type):

    def __getattr__(cls, name):
        try:
            code = cls.Codes.get_for_func(name)
        except AttributeError:
            raise AttributeError('Invalid Field Error Callable %s.' % name)
        else:
            def wrapped(**kwargs):
                return cls(code, **kwargs)
            return wrapped


class FieldError(ConfigError):

    def __init__(self, message, **kwargs):
        self.message = message

        self.ext = kwargs.pop('ext', None)
        self.context = kwargs

    def __str__(self):
        encoded = self.message.format(**self.context)
        if self.ext:
            return "%s\n%s" % (encoded, self.ext)
        return encoded


class FieldCodes(object):

    @classmethod
    def camel_case_split(cls, identifier):
        matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
        return [m.group(0) for m in matches]

    @classmethod
    def get_for_func(cls, name):
        """
        Instead of specifying a specific classmethod method initializing the
        exception with each code, this allows us to call arbitrary methods on
        the FieldError instance to instantiate a FieldError with the corresponding
        code:

        >>> raise FieldError.ExceedsMax(key, val, max)
        >>> err = FieldError(code=Codes.EXCEEDS_MAX, key, val, max)
        """
        parts = cls.camel_case_split(name)
        parts = [pt.upper() for pt in parts]
        val = '_'.join(parts)
        return getattr(cls, val)


field = '{field}'
value = '{value}'
for_field = 'for field {field}'
key = '{key}'


class ConfigFieldError(FieldError, metaclass=FieldErrorMeta):
    """
    Raised when a field is used improperly or validation fails.
    """
    TYPE_LOOKUP = {
        list: 'list',
        dict: 'dict',
        float: 'float',
        int: 'int',
        str: 'str',
    }

    class Codes(FieldCodes):

        # This shouldn't really be needed since we define all required fields in system settings.
        REQUIRED_FIELD = ConditionalString("The field", field, "is required.")
        EXCEEDS_MAX = ConditionalString("The value", for_field, 'exceeds the maximum', '({value} > {max})')
        EXCEEDS_MIN = ConditionalString("The value", for_field, 'exceeds the minimum', '({value} < {min})')
        DISALLOWED_VALUE = ConditionalString("The field", field, 'value', value, 'is not allowed')
        DISALLOWED_KEY = ConditionalString('The field', field, 'key', key, 'is not allowed')
        NON_CONFIGURABLE_FIELD = ConditionalString('The field', field, 'is not configurable')
        EXPECTED_FIELD_INSTANCE = ConditionalString('The field', field, 'is not a Field instance')
        UNEXPECTED_FIELD_INSTANCE = ConditionalString('The field', field, 'should not be a Field instance')
        FIELD_ALREADY_SET = ConditionalString('The field', field, 'was already set')
        CANNOT_ADD_FIELD = ConditionalString('The field', field, 'does not already exist and thus cannot be configured')
        CANNOT_ADD_CONFIGURABLE_FIELD = ConditionalString('Cannot add configurable field',
            field, 'to a non-configurable set')

    @classmethod
    def _find_types(cls, *args):
        for i in range(len(args)):
            if isinstance(args[i], tuple):
                return args[i], i
            elif isinstance(args[i], type):
                return args[i:], i
            else:
                continue
        return None

    @classmethod
    def _parse_referenced_types(cls, *args, **kwargs):
        """
        Unexpected vs. expected differs because unexpected type exceptions can
        be raised without referencing the types that were expected.  Expected
        type exceptions must reference what types were expected.

        Raises a TypeError if the types were not supplied as arguments for an
        expected type error.
        """
        expected = kwargs.pop('expected', False)

        types, index = cls._find_types(*args)
        if not types:
            if expected:
                raise TypeError('The expected types must be supplied as arguments.')

            if len(args) == 1:
                return None, args[0], None  # Return Without Key, With Value
            return args + (None, )   # Return With Key and Value

        # Types Supplied - Parse Key/Value Arguments
        # If no direct *args supplied, the key must be referenced as a keyword
        # argument, otherwise there is not enough context for the exception.
        leftover = args[:index]
        if len(leftover) == 2:
            return leftover + (types, )  # Return With Key and Value
        elif len(leftover) == 1:
            return None, leftover[0], types  # Return Without Key, With Value
        elif len(leftover) == 0:
            if 'key' not in kwargs:
                raise TypeError(
                    'The key must be provided as a keyword argument if not providing the value.'
                )
            return kwargs['key'], None, types  # Return With Key and Without Value
        else:
            raise TypeError('Invalid arguments supplied.')

    @classmethod
    def _get_unexpected_message(cls, key, value, types):
        if value:
            return ConditionalString(
                "Did not expect",
                'field `{key}`',
                'value {value}',
                'to be an instance of {value_type}'
                ', expected {types}'
            )
        return ConditionalString(
            "Did not expect",
            'field `{key}`',
            'to be an instance of {types},'
        )

    @classmethod
    def _get_expected_message(cls, key, value, types):
        if not types:
            raise TypeError('Types must be supplied as arguments for expected type exceptions.')
        return ConditionalString(
            'Expected',
            'field `{key}`',
            'to be an instance of {types}',
            ', not {value_type} (value={value})'
        )

    @classmethod
    def _get_message(cls, *args, **kwargs):
        expected = kwargs.pop('expected')
        key, value, types = cls._parse_referenced_types(*args, **kwargs)

        value_type = string_types = None
        if value:
            value_type = cls.TYPE_LOOKUP.get(type(value), str(type(value)))
        if types:
            string_types = humanize_list([
                cls.TYPE_LOOKUP[tp] for tp in types], conjunction='or')

        if expected:
            MESSAGE = cls._get_expected_message(key, value, types)
        else:
            MESSAGE = cls._get_unexpected_message(key, value, types)

        return MESSAGE.format(
            key=key,
            value_type=value_type,
            value=value,
            types=string_types,
        )

    @classmethod
    def UnexpectedType(cls, *args, **kwargs):
        """
        When referencing an error due to an unexpected type, the method can
        be called in thee following ways:

        (1) ConfigFieldError.UnexpectedType(value)
            - Infers invalid type based on supplied value.
            - Notes the type was unexpected.

            >>> Did not expect value 1 to be an instance of int.

        (2) ConfigFieldError.UnexpectedType(value, *types)
            - Infers invalid type based on supplied value.
            - Notes that it is not what was expected, in *types.

            >>> Did not expect value 4 to be an instance of int, expected
                list or dict.

        (3) ConfigFieldError.UnexpectedType(key, value)
            - Infers invalid type based on supplied value.
            - References key that value is associated with.

            >>> Did not expect field `some_key` to be an instance of int.

        (4) ConfigFieldError.UnexpectedType(key, value, **types)
            - Infers invalid type based on supplied value.
            - Notes that it is not what was expected, in *types.
            - References key that value is associated with.

            >>> Did not expect field `some_key` to be an instance of int
                (value=4), expected list or dict.

        (5) ConfigFieldError.UnexpectedType(**types, key='some_key')
            - References that we did not expect the type provided at `key`
              to be an instance of *types.

            >>> Did not expect field `key` to be an instance of list or dict.

        Location of values is intelligently determined based on the presence
        of the first argument in *args that is an instance of type.

        [x] NOTE:
        --------
        The primary difference between argument schema for UnexpectedType vs.
        ExpectedType is that for ExpectedType, the types are always required,
        since we cannot note what was expected without them.
        """
        kwargs['expected'] = False
        message = cls._get_message(*args, **kwargs)
        return cls(message, **kwargs)

    @classmethod
    def ExpectedType(cls, *args, **kwargs):
        """
        When referencing an error due to an expected type that was not seen,
        the method can be called in thee following ways:

        (1) ConfigFieldError.ExpectedType(value, *types)
            - Infers invalid type received based on supplied value.
            - Notes that it is not what was expected, in *types.

            >>> Expected value 4 to be an instance of dict, not int.

        (2) ConfigFieldError.ExpectedType(key, value, *types)
            - Infers invalid type received based on supplied value.
            - References key that value is associated with.
            - Notes that it is not what was expected, in *types.

            >>> Expected field `some_key` to be an instance of dict or list,
                not int (value=4).

        (3) ConfigFieldError.ExpectedType(value, **types)
            - Infers invalid type received based on supplied value.
            - Notes that it is not what was expected, in *types.

            >>> Expected value 4 to be an instance of dict, not int.

        (4) ConfigFieldError.ExpectedType(**types, key='some_key')
            - References that we expected but did not receive a type in **types
              for key `key`.

            >>> Expected field `some_key` to be an instance of list or dict.

        Location of values is intelligently determined based on the presence
        of the first argument in *args that is an instance of type.

        [x] NOTE:
        --------
        The primary difference between argument schema for UnexpectedType vs.
        ExpectedType is that for ExpectedType, the types are always required,
        since we cannot note what was expected without them.
        """
        kwargs['expected'] = True
        message = cls._get_message(*args, **kwargs)
        return cls(message, **kwargs)
