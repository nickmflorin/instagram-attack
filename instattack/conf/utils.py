from argparse import ArgumentTypeError
from cerberus import Validator
from plumbum.path import LocalPath, Path

from instattack import settings
from instattack.exceptions import ConfigurationError


def validate_log_level(val):
    try:
        val = str(val)
    except TypeError:
        raise ArgumentTypeError("Invalid log level.")
    else:
        if val.upper() not in settings.LEVELS:
            raise ArgumentTypeError("Invalid log level.")
        return val.upper()


def validate_config_filepath(value):
    """
    Validates the path specified or defaulted for the configuration file.  If the
    file cannot be found at the top level of the application, it will check the
    path as an absolute path on the local machine.

    TODO
    ----
    For error messages, indicate whether or not the path error was because we
    couldn't find it in the root directory or because the specified path was
    invalid.

    We might not need all of the validations for each case, maybe just the
    last two.
    """
    def _validate_path(path):
        if not path.dirname.exists():
            raise ArgumentTypeError(f'The path {value} does not exist.')

        if path.exists() and not path.is_file():
            raise ArgumentTypeError(f'The path {value} does not specify a config file.')

        if path.suffix not in ('.yml', '.yaml'):
            raise ArgumentTypeError('The configuration file must be a YAML file.')

        if not path.exists():
            if path.suffix == '.yml':
                path = path.with_suffix('.yaml')
            else:
                path = path.with_suffix('.yml')

        if not path.exists():
            raise ArgumentTypeError(f'The path {value} does not exist.')
        return settings.DIR_STR(path)

    root_path = settings.GET_ROOT() / Path(value)
    try:
        return _validate_path(root_path)
    except ArgumentTypeError:
        root_path = LocalPath(value)
        try:
            return _validate_path(root_path)
        except ArgumentTypeError as e:
            raise e


def validate_config_schema(config):
    """
    Using Cerebrus Package

    http://docs.python-cerberus.org/en/stable/schemas.html
    """
    from instattack import logger
    log = logger.get_sync(__name__, subname='validate_config_schema')

    log.debug('Validating Schema Config')

    def positive_int(**kwargs):
        config = {
            'required': True,
            'type': 'integer',
            'min': 0,
        }
        config.update(**kwargs)
        return config

    def boolean():
        return {
            'required': True,
            'type': 'boolean'
        }

    config.setdefault('silent_shutdown', True)

    config.setdefault('login', {})
    config['login'].setdefault('limit', None)
    config['login'].setdefault('log', False)
    config['login'].setdefault('remove_proxy_on_error', False)

    v = Validator()
    v.schema = {
        'silent_shutdown': {
            'required': True,
            'type': 'boolean'
        },
        'login': {
            'required': True,
            'type': 'dict',
            'schema': {
                'limit': positive_int(max=10000, nullable=True),
                'batch_size': positive_int(max=100),
                'log': boolean(),
                'remove_proxy_on_error': boolean(),
                'attempts': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'batch_size': positive_int(max=100),
                        'log': boolean(),
                    }
                },
                'connection': {
                    'required': True,
                    'type': 'dict',
                    'schema': {
                        'limit_per_host': positive_int(max=10),
                        'timeout': positive_int(max=20),
                        # Might want to raise this max value higher.
                        'limit': positive_int(max=200),
                    }
                }
            }
        }
    }

    # log.info(config['silent_shutdown'])
    validated = v.validate(config)
    if not validated:
        raise ConfigurationError(v.errors)
