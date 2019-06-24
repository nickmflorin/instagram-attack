import os
from cerberus import Validator
from pathlib import Path

from simple_settings import LazySettings
from instattack.ext import get_root

from .schema import Schema
from .exceptions import ConfigError
from .doc import ConfigDoc


class LazierSettings(LazySettings):
    """
    We override the simple_settings `LazySettings` module to introduce some
    convenience case insensitivity and methods for getting and setting the
    settings lazily.

    [x] TODO:
    --------
    We might be able to get rid of the functionality in the Config object all
    together if we just use this module.  We could override the update method
    too.
    """
    ENV_VAR = 'INSTATTACK_SIMPLE_SETTINGS'
    SETTINGS_DIR = ('instattack', 'config', '_settings', )

    def __init__(self):
        """
        When settings are initially loaded, ICONS, COLORS, TEXT and FORMATS
        sections will all be plain old dict(s).  We want to convert them to
        ConfigDoc instances so we can leverage the overridden dict behavior.

        [x] TODO:
        --------
        This will be reserved for loading the default system settings (defined
        by developer) and not the possible overridden user settings.  This means
        that we don't **have** to validate the settings, but we probably should
        use Cerberus anyways.
        """

        # Let easy_settings Handle Loading of Setting Values
        settings_path = self.get_settings_path()
        super(LazierSettings, self).__init__(settings_path)

        # Configure Settings with Config Doc Instances
        # TODO: Figure out how to turn instattack settings into ConfigDoc
        # instances.
        data = self.as_dict()
        doc = ConfigDoc(**data)
        self.initialize(doc)
        import ipdb; ipdb.set_trace()

    @classmethod
    def __SETTINGS_FILE__(cls, default='dev'):
        """
        Sets the default settings file to the ENV variable if no ENV variable
        set, otherwise, returns the settings file defined by the previously
        set ENV variable.

        This is important for top-level functionality like setuptools, where
        we might want to define `TERMX_SIMPLE_SETTINGS` before loading the
        module.
        """
        if not os.environ.get(cls.ENV_VAR):
            os.environ[cls.ENV_VAR] = default
        return os.environ[cls.ENV_VAR]

    def get_settings_path(cls):
        """
        Validates whether or not the setup settings file exists at the location
        given by SETUP_SETTINGS and formats the filepath into a suitable string
        for simple_settings.

        If the settings file exists, returns the simple_settings formatted version.

        Returns a string formatted as "<parent_dir>.<dir>.<settings_file>" where
        `settings_file` does not have an extension.
        """
        settings_file = cls.__SETTINGS_FILE__()

        root = get_root(NAME='instattack')
        settings_root = os.path.join(str(root), *cls.SETTINGS_DIR)
        settings_file_path = os.path.join(settings_root, "%s.py" % settings_file)

        settings_path = Path(settings_file_path)
        if not settings_path.is_file():
            raise RuntimeError('Installation settings file missing at %s.' % settings_file_path)

        # Last Component is Extension-less for simple_settings
        simple_settings_path = ("%s.%s" % (
            '.'.join(cls.SETTINGS_DIR),
            settings_path.name.replace(settings_path.suffix, '')
        ))
        print("Using Settings %s" % simple_settings_path)
        return simple_settings_path

    def __getattr__(self, attr):
        """
        Override to provide case in-sensitivity.

        We do not have to worry about the dynamic_reader property, since we are
        not using that.
        """
        self.setup()
        try:
            result = self._dict[self.__keytransform__(attr)]
        except KeyError:
            raise AttributeError('You did not set {} setting'.format(attr))

        return result

    def initialize(self, *args, **kwargs):
        """
        Same logic as `configure` but does not expect the COLORS, ICONS, TEXT
        and FORMATS objects to already bet present.  This should only be called
        once.
        """
        self.setup()

        data = dict(*args, **kwargs)
        for key, val in data.items():
            print('Updating %s' % key)
            key = self.__keytransform__(key)
            self._dict.update(**{key: val})

    def configure(self, *args, **kwargs):
        """
        Override simple_settings's configure method to build in the non-destructive
        dict update methods inherent in the ConfigDoc instances.

        Expects that COLORS, ICONS, TEXT and FORMATS attributes are already set
        as ConfigDoc instances.

        Original Method:

        >>>  self.setup()
        >>>  self._dict.update(settings)
        >>>  if self._dynamic_reader:
        >>>     for key, value in settings.items():
        >>>         self._dynamic_reader.set(key, value)

        We do not have to worry about the dynamic_reader property, since we are
        not using that.

        [x] TODO:
        --------
        We need to perform some sort of config validation here.  We should use
        the Cerberus package and define the schema.  This will also work for
        the styling attributes as well.

        [x] NOTE:
        --------
        We have to access attributes on `Settings` instead of using Settings.as_dict().
        This is because Settings.as_dict() will also call the __dict__ methods
        on ConfigDoc instances, converting them to plain old dicts.
        """

        # Setup if Not Initialized (Should be by now)
        self.setup()

        override = dict(*args, **kwargs)
        for key, val in override.items():
            key = self.__keytransform__(key)

            # TODO: Make Update Work Recursively
            self._dict.update(**{key: val})

            # if key in self.CUSTOM_DOCS:
            #     try:
            #         getattr(self.settings, key)
            #     except AttributeError:
            #         raise ConfigError(f"{key} was never configured!")

            #     doc = getattr(self.settings, key)
            #     if not isinstance(doc, ConfigDoc):
            #         raise ConfigError(f"{key} should have been configured as ConfigDoc!")

            #     # Non-destructive update
            #     doc.update(**val)
            #     self._dict.update(**{key: doc})
            # else:
            #     self._dict.update(**{key: val})

    def __keytransform__(self, key):
        return key.upper()

    # def override_with_args(self, args):

    #     def recusively_update(data, argkey, argval):
    #         for key, val in data.items():
    #             if isinstance(val, dict):
    #                 recusively_update(val, argkey, argval)
    #             else:
    #                 if key == argkey:
    #                     data[key] = argval

    #     for argkey, argval in args:
    #         recusively_update(self, argkey, argval)

    # def validate(self, conf):
    #     """
    #     Validates the configuration to be of the correct schema and then sets the
    #     global config object to the validated schema.

    #     Note that the global config object is just a dictionary, where as the config
    #     object used by Cement is a custom object that behaves similarly to a dict.
    #     For our purposes, the difference is not important.

    #     Using Cerebrus Package
    #     http://docs.python-cerberus.org/en/stable/schemas.html
    #     """
    #     v = Validator()

    #     v.schema = Schema
    #     validated = v.validate(conf)

    #     if not validated:
    #         raise ConfigSchemaError(v.errors)
