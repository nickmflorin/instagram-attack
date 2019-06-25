import re
from termx import settings
from instattack.core.exceptions import InstattackError


class ConfigError(InstattackError):
    pass


class ConfigValueError(ConfigError):
    """
    Not currently used, but we will hold onto just in case we want to reference
    a more general field error.
    """

    def __init__(self, value, ext=None):
        self.value = value
        self.ext = ext

    def __str__(self):
        if not self.ext:
            return f"Invalid configuration value {self.value}."
        return f"Invalid configuration value {self.value}; {self.ext}"


class FieldErrorMeta(type):

    def __getattr__(cls, name):
        try:
            code = cls.Codes.get_for_func(name)
        except AttributeError:
            raise AttributeError('Invalid Field Error Callable %s.' % name)
        else:
            def wrapped(*args, **kwargs):
                return cls(code, *args, **kwargs)
            return wrapped


class FieldError(ConfigError):

    def __init__(self, code, *args, **kwargs):
        self.code = code
        self.msg_args = args
        self.ext = kwargs.get('ext')

    def __str__(self):
        encoded = self.code % self.msg_args
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


class FieldValidationError(FieldError, metaclass=FieldErrorMeta):
    """
    Raised when a field does not validate properly.
    """

    class Codes(FieldCodes):

        EXCEEDS_MAX = "The value for field %s exceeds the maximum (%s > %s)."
        EXCEEDS_MIN = "The value for field %s exceeds the minimum (%s < %s)."
        EXPECTED_INT = "Expected an integer for field %s, not %s."
        EXPECTED_FLOAT = "Expected a float for field %s, not %s."
        EXPECTED_DICT = "Expected a dict for field %s, not %s."
        EXPECTED_LIST = "Expected a list for field %s, not %s."

    @classmethod
    def ExpectedType(cls, key, value, type):
        types = {
            list: cls.ExpectedList,
            dict: cls.ExpectedDict,
            float: cls.ExpectedFloat,
            int: cls.ExpectedInt,
        }
        return types[type](key, value)


class ConfigFieldError(FieldError, metaclass=FieldErrorMeta):
    """
    Raised when a field is used improperly.
    """
    class Codes(FieldCodes):

        # This shouldn't really be needed since we define all
        # required fields in system settings.
        REQUIRED_FIELD = "The field %s is required."

        NON_CONFIGURABLE_FIELD = "The field %s is not configurable."
        EXPECTED_FIELD_INSTANCE = "The provided field %s should be a Field instance."
        FIELD_ALREADY_SET = "The provided field %s was already set."
        CANNOT_ADD_FIELD = "The field %s does not exist in settings and cannot be configured."
        CANNOT_ADD_CONFIGURABLE_FIELD = "Cannot add configurable field %s to a non-configurable set."


class ConfigSchemaError(Exception):
    """
    [!] Temporarily Deprecated
    ----------------------
    We are not currently using Cerberus schema validation.

    Used to convert Cerberus schema validation errors into more human readable
    series of errors, each designated on a separate line.
    """

    def __init__(self, errors):
        self.errors = errors

    def __str__(self):
        return "\n" + "\n" + self.humanize_errors(self.errors) + "\n"

    def humanize_error_list(self, error_list, prev_key=None):
        errs = []

        for err in error_list:
            if not isinstance(err, str):
                errs.extend(self.convert_errors(err, prev_key=prev_key))
            else:
                errs.append(err)
        return errs

    def convert_errors(self, error_dict, prev_key=None):
        errors = []
        prev_key = prev_key or ""

        for key, value in error_dict.items():
            if prev_key:
                new_key = f"{prev_key}.{key}"
            else:
                new_key = key

            if len(value) == 1 and type(value[0]) is str:
                errors.append((new_key, value[0]))
            else:
                errs = self.humanize_error_list(value, prev_key=new_key)
                errors.extend(errs)
        return errors

    def humanize_errors(self, errors):
        tuples = self.convert_errors(errors)

        humanized = []
        for error in tuples:

            label_formatter = settings.Colors.MED_GRAY
            formatted_attr = settings.Colors.BLACK.format(bold=True)(error[0])
            formatted_error = settings.Colors.ALT_RED.format(bold=True)(error[1].title())

            humanize = (
                f"{label_formatter('Attr')}: {formatted_attr} "
                f"{label_formatter('Error')}: {formatted_error}"
            )
            humanized.append(humanize)
        return "\n".join(humanized)
