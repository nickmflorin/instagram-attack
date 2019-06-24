import copy

from .exceptions import ConfigValueError
from .fields import Field, SetField, DictField


class ConfigDoc(dict):
    """
    Dict subclass specifically for configuration that adds flexibility to how
    items are retrieved and stores keys and values by uppercase transformations.
    """

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __getattr__(self, key):
        return self.__getitem__(key)

    def __getitem__(self, key):
        """
        We do not want to return a `value` attribute for the SetField since
        it does not have a `value` attribute, but represents a series of fields
        with individual values.
        """
        value = super(ConfigDoc, self).__getitem__(self.__keytransform__(key))
        if isinstance(value, Field) and not isinstance(value, SetField):
            return value.value
        return value

    def __setitem__(self, key, value):
        super(ConfigDoc, self).__setitem__(
            self.__keytransform__(key),
            value
        )

    def __delitem__(self, key):
        super(ConfigDoc, self).__delitem__(self.__keytransform__(key))

    def __keytransform__(self, key):
        return key.upper()

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
        raw = {}
        for key, val in self.items():
            if isinstance(val, ConfigDoc):
                raw[key] = val.__deepcopy__(memo)
            else:
                raw[key] = copy.deepcopy(val)
        return raw

    def configure(self, *args, **kwargs):
        """
        SetField instances represent a series of configurable fields, so when
        updating, we want to ensure the type is a dict and update each field
        individually.

        For plain old DictField instances, we replace the entire value of the
        field, since these fields are meant to be configurable, but not updatable
        key by key.
        """
        for k, v in dict(*args, **kwargs).items():
            if k in self:
                if isinstance(self[k], dict):
                    raise RuntimeError('Dict instances should not be stored in Doc.')

                if isinstance(self[k], Field):
                    if isinstance(self[k], SetField):
                        if not isinstance(v, dict):
                            raise ConfigValueError(v, ext='Must configure SetField with dict instance.')
                        self[k].configure(**v)

                    # Only Purpose of Separating Out: To ensure that we are not
                    # updating other fields with dict instances, since that can
                    # get hairy/confusing.
                    elif isinstance(self[k], DictField):
                        self[k].configure(v)

                    else:
                        if isinstance(v, dict):
                            raise ConfigValueError(v,
                                ext='Cannot configure %s with dict instance.' % self[k].__class__.__name__)
                        self[k].configure(v)
                else:
                    self.__setitem__(k, v)
            else:
                self.__setitem__(k, v)

    def update(self, *args, **kwargs):
        """
        SetField instances represent a series of configurable fields, so when
        updating, we want to ensure the type is a dict and update each field
        individually.

        For plain old DictField instances, we replace the entire value of the
        field, since these fields are meant to be configurable, but not updatable
        key by key.
        """
        for k, v in dict(*args, **kwargs).items():
            if k in self:
                if isinstance(self[k], dict):
                    raise RuntimeError('Dict instances should not be stored in Doc.')

                if isinstance(self[k], Field):
                    if isinstance(self[k], SetField):
                        if not isinstance(v, dict):
                            raise ConfigValueError(v, ext='Must update SetField with dict instance.')
                        self[k].update(**v)
                    else:
                        if isinstance(v, dict):
                            raise ConfigValueError(v,
                                ext='Cannot update %s with dict instance.' % self[k].__class__.__name__)
                        self[k].update(v)
                else:
                    self.__setitem__(k, v)
            else:
                self.__setitem__(k, v)
