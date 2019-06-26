class SettingsDict(dict):
    """
    Defines the general dict interface for allowing the structures that contain
    our settings to be accessible and settable without case sensitivity and
    with attribute access.
    """

    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __keytransform__(self, key):
        return key.upper()

    def update(self, *args, **kwargs):
        for key, val in dict(*args, **kwargs).items():
            self.__setitem__(key, val)

    def __getitem__(self, key):
        key = self.__keytransform__(key)
        try:
            return super(SettingsDict, self).__getitem__(key)
        except KeyError:
            raise AttributeError('You did not set {} setting'.format(key))

    def __getattr__(self, key):
        return self.__getitem__(key)

    def __setitem__(self, key, value):
        super(SettingsDict, self).__setitem__(self.__keytransform__(key), value)

    def __contains__(self, key):
        key = self.__keytransform__(key)
        return super(SettingsDict, self).__contains__(key)

    def __delitem__(self, key):
        super(SettingsDict, self).__delitem__(self.__keytransform__(key))


class SettingsFieldDict(SettingsDict):
    """
    Maintains a parallel set of fields that maps directly to the dict structure.

    This is so that we can access the field objects themselves at any given
    nesting level, in addition to the values of the field objects from the
    regular dict.
    """

    def __init__(self, *args, **kwargs):
        """
        When we access values on the settings instance, they do not return
        the raw field objects but return the .value property of those field
        objects.  We want to be able to access the nested fields as well, so
        that we can easily configure fields nested several layers deep.

        If we didn't set `fields` as a separate attribute, we could not do:
            >>> settings.field1.field2.configure(value=1)
        because each getattr would call __getitem__ which returns the field
        value.
        """
        super(SettingsFieldDict, self).__init__(*args, **kwargs)
        self.fields = SettingsDict(*args, **kwargs)

    def __getfield__(self, key):
        return self.fields.__getitem__(key)

    def __getattr__(self, key):
        if key == 'fields':
            return self.fields
        return self.__getitem__(key)

    def __setitem__(self, key, value):
        self.fields.__setitem__(key, value)
        super(SettingsFieldDict, self).__setitem__(self.__keytransform__(key), value)

    def __getitem__(self, key):
        """
        Attribute access returns the field value, unless the field is a SetField.

        We do not want to return a `value` attribute for the SetField since
        it does not have a `value` attribute, but represents a series of fields
        with individual values.
        """
        field = super(SettingsFieldDict, self).__getitem__(key)
        if hasattr(field, 'value'):
            return field.value
        return field
