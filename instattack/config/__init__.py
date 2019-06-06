from cement import init_defaults
from cerberus import Validator
import importlib
import os
import signal

from instattack.app.exceptions import ConfigurationError

from .settings import APP_NAME, ROOT_DIR
from .schema import Schema


_configuration = {}


class _Config(dict):

    settings = importlib.import_module('.settings', package=__name__)

    __CONFIG_SECTION__ = APP_NAME

    __CONFIG__ = init_defaults(APP_NAME)
    __CONFIG__[APP_NAME]['debug'] = False
    __CONFIG__[APP_NAME]['log.logging'] = {'level': 'info'}

    __CONFIG_DIRS__ = [os.path.join(ROOT_DIR, 'config')]
    __CONFIG_FILES__ = [f'{APP_NAME}.yml']

    __EXTENSIONS__ = ['yaml', 'colorlog', 'jinja2']
    __CONFIG_HANDLER__ = 'yaml'
    __CONFIG_FILE_SUFFIX__ = '.yml'

    __LOG_HANDLER__ = 'colorlog'
    __OUTPUT_HANDLER__ = 'jinja2'

    __EXIT_ON_CLOSE__ = True

    __SIGNALS__ = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

    def __init__(self, data):
        super(_Config, self).__init__(data)

        # Used to prevent race conditions in the global application shutdown
        # with asyncio.
        self.shutdown = False

    def set(self, data):
        self.update(**data)

    def override_with_args(self, args):

        def recusively_update(data, argkey, argval):
            for key, val in data.items():
                if isinstance(val, dict):
                    recusively_update(val, argkey, argval)
                else:
                    if key == argkey:
                        data[key] = argval

        for argkey, argval in args:
            recusively_update(self, argkey, argval)

    def validate(self, conf, set=True):
        """
        Validates the configuration to be of the correct schema and then sets the
        global config object to the validated schema.

        Note that the global config object is just a dictionary, where as the config
        object used by Cement is a custom object that behaves similarly to a dict.
        For our purposes, the difference is not important.

        Using Cerebrus Package
        http://docs.python-cerberus.org/en/stable/schemas.html
        """
        v = Validator()

        v.schema = Schema
        validated = v.validate(conf)

        if not validated:
            raise ConfigurationError(v.errors)

        if set:
            self.update(**conf)


config = _Config({})
