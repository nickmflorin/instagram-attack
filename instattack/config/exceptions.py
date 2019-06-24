from termx import settings
from instattack.core.exceptions import InstattackError


class ConfigError(InstattackError):
    pass


class ConfigValueError(ConfigError):
    def __init__(self, value, ext=None):
        self.value = value
        self.ext = ext

    def __str__(self):
        if not self.ext:
            return f"Invalid configuration value {self.value}."
        return f"Invalid configuration value {self.value}; {self.ext}"


class FieldError(ConfigError):

    EXCEEDS_MAX = "The value for field %s exceeds the maximum (%s > %s)."
    EXCEEDS_MIN = "The value for field %s exceeds the minimum (%s < %s)."
    EXPECTED_INT = "Expected an integer for field %s, not %s."
    EXPECTED_FLOAT = "Expected a float for field %s, not %s."
    EXPECTED_DICT = "Expected a dict for field %s, not %s."
    EXPECTED_LIST = "Expected a list for field %s, not %s."
    REQUIRED_FIELD = "The field %s is required."
    NON_CONFIGURABLE_FIELD = "The field %s is not configurable."
    UNEXPECTED_SET_FIELD = "The field %s does not belong in the set."
    EXPECTED_FIELD_INSTANCE = "The provided field %s should be a Field instance."
    FIELD_ALREADY_SET = "The provided field %s was already set."

    def __init__(self, code, *args):
        self.code = code
        self.msg_args = args

    def __str__(self):
        return self.code % self.msg_args

    @classmethod
    def FieldAlreadySet(cls, key):
        return FieldError(cls.FIELD_ALREADY_SET, key)

    @classmethod
    def ExpectedFieldInstance(cls, key):
        return FieldError(cls.EXPECTED_FIELD_INSTANCE, key)

    @classmethod
    def UnexpectedSetField(cls, key):
        return FieldError(cls.UNEXPECTED_SET_FIELD, key)

    @classmethod
    def NonConfigurableField(cls, key):
        return FieldError(cls.NON_CONFIGURABLE_FIELD, key)

    @classmethod
    def ExceedsMax(cls, key, value, max):
        return FieldError(cls.EXCEEDS_MAX, key, value, max)

    @classmethod
    def ExceedsMin(cls, key, value, min):
        return FieldError(cls.EXCEEDS_MIN, key, value, min)

    @classmethod
    def ExpectedInt(cls, key, value):
        return FieldError(cls.EXPECTED_INT, key, value)

    @classmethod
    def ExpectedFloat(cls, key, value):
        return FieldError(cls.EXPECTED_FLOAT, key, value)

    @classmethod
    def ExpectedList(cls, key, value):
        return FieldError(cls.EXPECTED_LIST, key, value)

    @classmethod
    def ExpectedDict(cls, key, value):
        return FieldError(cls.EXPECTED_DICT, key, value)

    @classmethod
    def ExpectedType(cls, key, value, type):
        types = {
            list: cls.ExpectedList,
            dict: cls.ExpectedDict,
            float: cls.ExpectedFloat,
            int: cls.ExpectedInt,
        }
        return types[type](key, value)

    @classmethod
    def RequiredField(cls, key):
        return FieldError(cls.REQUIRED_FIELD, key)


class ConfigSchemaError(Exception):
    """
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
