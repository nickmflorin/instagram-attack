import importlib
import inspect
import os
from pathlib import Path
import sys

from instattack.ext import get_root

from .exceptions import ConfigFieldError, ConfigError
from .fields import Field, SetField
from .utils import SettingsFieldDict


class LazySettings(SettingsFieldDict):
    """
    Adopted from simple_settings module
    < https://github.com/drgarcia1986/simple-settings >
    """

    ENVIRON_KEYS = ('INSTATTACK_SIMPLE_SETTINGS', )
    COMMAND_LINE_ARGS = ('--settings', '--instattack-settings')
    SETTINGS_DIR = ('instattack', 'config', '_settings', )

    def __init__(self, *settings_list):
        """
        Initializes the settings with the optionally passed in settings list.
        If the settings list is not provided, it will be retrieved from either
        the ENV variables or command line arguments when being initialized.

        When we access values on the settings instance, they do not return
        the raw field objects but return the .value property of those field
        objects.  We have to initialize SettingsFieldDict to have the .fields
        attribute to track the field objects themselves.
        """
        self._settings_list = list(settings_list)
        self._initialized = False
        super(LazySettings, self).__init__({})

    def __getitem__(self, key):
        self.setup()  # Force Setup if Not Initialized
        return super(LazySettings, self).__getattr_(key)

    def setup(self):
        """
        Checks if the settings list was provided to LazySettings on initialization,
        and if not, retrieves the settings list based on either the ENV vars
        or command line arguments.

        After the settings file is retrieved, loads the settings stored in
        each file.
        """
        if self._initialized:
            return

        if not self._settings_list:
            self._settings_list = self._get_settings_paths()
            if not self._settings_list:
                raise RuntimeError('Settings are not configured')

        self._load_settings_pipeline()
        self._initialized = True

    def update(self, *args, **kwargs):
        """
        Sets the initial settings based on system defined settings in the
        corresponding settings files.

        This is only called once, to initially populate the settings.  Any changes
        to the settings afterwards must be done with the .configure() method.

        [x] NOTE:
        --------
        On init, in order to set the `fields` attribute, we have to call:
            >>> super(LazierSettings, self).__init__({})

        This will call the update() method.

        In order to prevent multiple initial updates for LazySettings, we will
        only udpate if there is data present (since there is none on init).
        """
        if args or kwargs:
            if self._initialized:
                raise RuntimeError('Can only call update one time.')

            for k, v in dict(*args, **kwargs).items():
                if k in self:
                    raise ConfigFieldError.FieldAlreadySet(k)
                self.__setitem__(k, v)

    def configure(self, *args, **kwargs):
        """
        After LazySettings are populated initially, using the .update() method,
        the only way to make changes to the settings is to use the .configure()
        method.

        This method is used primarily for configuring the system settings loaded
        on initialization with overridden settings provided by the user.

        Since this is used for updating the settings by the user, we do not allow
        (1) Configuring fields that are not already present
        (2) Configuring fields that are constants (not Field instances)
                - Values that are not instances of Field are non-configurable
                  by default.

        Field instances that are non-configurable will throw exceptions when
        the configure method is called.

        [!] IMPORTANT
        ------------
        We must access the raw fields, i.e. not using self[k] to get the field
        values, because we need to access the field methods and properties.
        """
        self.setup()   # Force Setup if Not Initialized

        raise ConfigFieldError.ExpectedType('test', 'not-a-dict', dict,
                        ext='SetField(s) must be configured with dict instance.')

        for k, v in dict(*args, **kwargs).items():

            # Do Not Allow Additional Fields to be Added to Settings
            if k not in self:
                raise ConfigFieldError.CannotAddField(k)

            field = self.__getfield__(k)

            # Do Not Allow Configuring of Constants & Check Field Configurability
            # at Top Level
            if not isinstance(field, Field) or not field.configurable:
                raise ConfigFieldError.NonConfigurableField(k)

            # [x] TODO: To be more consistent, we might just want to plugin
            # the dict directly and not use the keyword arg method.
            if isinstance(field, SetField):
                if not isinstance(v, dict):
                    raise ConfigFieldError.ExpectedType(k, v, dict,
                        ext='SetField(s) must be configured with dict instance.')
                field.configure(**v)
            else:
                field.configure(v)

    @staticmethod
    def _is_valid_file(file_name):
        """
        These are taken from the simple_settings.strategires PythonStrategy
        module, and we want to include them directly since we do not have to
        worry about other strategies.

        We also want to tweak them a tiny bit.
        """
        try:
            importlib.import_module(file_name)
        except (ImportError, TypeError) as e:
            return e

    @staticmethod
    def _load_settings_file(settings_file):
        """
        These are taken from the simple_settings.strategires PythonStrategy
        module, and we want to include them directly since we do not have to
        worry about other strategies.

        We also want to tweak them a tiny bit.
        """
        result = {}
        module = importlib.import_module(settings_file)
        for setting in (s for s in dir(module) if not s.startswith('_')):
            setting_value = getattr(module, setting)
            if not inspect.ismodule(setting_value):

                # Ignore Import Statements of Functions
                if not inspect.isfunction(setting_value):
                    result[setting] = setting_value
        return result

    def _load_settings_pipeline(self):
        """
        These are taken from the simple_settings.strategires PythonStrategy
        module, and we want to include them directly since we do not have to
        worry about other strategies.

        Original code would check strategy and use strategy to load file:
        >>> strategy = self._get_strategy_by_file(settings_file)
        >>> strategy.load_settings_file(...)

        We don't have to worry about that, since we are restricting to .py files
        for config.
        """
        for settings_file in self._settings_list:
            exc = self._is_valid_file(settings_file)
            if exc:
                raise ConfigError(
                    f'\nInvalid settings file [{settings_file}]'
                    f"\n{exc.__class__.__name__}: {exc}"
                )

            settings = self._load_settings_file(settings_file)
            self.update(settings)

    @classmethod
    def _get_settings_paths(cls):
        """
        Validates whether or not the setup settings file exists at the location
        given by SETUP_SETTINGS and formats the filepath into a suitable string
        for simple_settings.

        If the settings file exists, returns the simple_settings formatted version.

        Returns a string formatted as "<parent_dir>.<dir>.<settings_file>" where
        `settings_file` does not have an extension.
        """
        settings_files = cls._get_settings_from_cmd_line()
        if not settings_files:
            settings_files = cls._get_settings_from_environ()

        return [cls._convert_settings_to_module(file) for file in settings_files]

    @classmethod
    def _convert_settings_to_module(cls, settings_file):

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

    @classmethod
    def _get_settings_from_environ(cls, default='dev'):
        """
        Sets the default settings file to the ENV variable if no ENV variable
        set, otherwise, returns the settings file defined by the previously
        set ENV variable.

        This is important for top-level functionality like setuptools, where
        we might want to define `TERMX_SIMPLE_SETTINGS` before loading the
        module.

        [x] TODO:
        --------
        We probably don't need multiple environment variables here.
        """
        settings_files = []
        for env_key in cls.ENVIRON_KEYS:
            if env_key in os.environ:
                settings_files.append(os.environ[env_key])

        if len(settings_files) == 0:
            for env_key in cls.ENVIRON_KEYS:
                os.environ[env_key] = default
            settings_files.append(default)

        return settings_files

    @classmethod
    def _get_settings_from_cmd_line(cls):
        for arg in sys.argv[1:]:
            for lib_arg in cls.COMMAND_LINE_ARGS:
                if arg.startswith(lib_arg):
                    try:
                        return arg.split('=')[1]
                    except IndexError:
                        return

    def configure_token(self, token):
        self.fields.instagram.request.headers.configure({'X-CSRFToken': token})

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
